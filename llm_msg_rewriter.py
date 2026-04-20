import json
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import requests

# ====================== 全局日志配置（可复用资产） ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ====================== 1. 配置中心（LLM专属，可配置化） ======================
@dataclass
class LLMConfig:
    """LLM模型服务配置类"""
    api_key: Optional[str] = "sk-898f757847b0461da3d48***********"
    base_url: str = "https://api.deepseek.com/v1/chat/completions"
    model: str = "deepseek-chat"
    temperature: float = 0.1  # 低温度保证改写精准，不跑偏
    top_p: float = 0.3
    repetition_penalty: float = 1.0
    max_tokens: int = 2048
    timeout: int = 60
    max_retry: int = 3  # 接口失败自动重试

@dataclass
class ProcessConfig:
    """批量文本处理配置"""
    max_workers: int = 8    # 并发线程数（适配LLM接口限流，不建议过高）
    batch_size: int = 10    # 每批处理10行，平衡效率与格式稳定性
    file_encoding: str = "utf-8"

# ====================== 2. LLM专用LLM客户端（生产级可复用） ======================
class LLMChatClient:
    """LLM API对接客户端，兼容批量改写、重试、格式校验"""
    def __init__(self, config: LLMConfig):
        self.config = config
        self.headers = {
            "Content-Type": "application/json"
        }
        if self.config.api_key:
            self.headers["Authorization"] = f"Bearer {self.config.api_key}"
            
        logger.info(f"LLM客户端初始化完成，模型：{config.model}，地址：{config.base_url}")

    def _send_request(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """带重试的单轮API请求"""
        for retry in range(self.config.max_retry):
            try:
                payload = {
                    "model": self.config.model,
                    "messages": messages,
                    "temperature": self.config.temperature,
                    "top_p": self.config.top_p,
                    "repetition_penalty": self.config.repetition_penalty,
                    "max_tokens": self.config.max_tokens
                }
                resp = requests.post(
                    url=self.config.base_url,
                    headers=self.headers,
                    json=payload,
                    timeout=self.config.timeout
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.warning(f"LLM请求失败，第{retry+1}次重试：{str(e)}")
                if retry == self.config.max_retry - 1:
                    logger.error(f"最终请求失败：{str(e)}")
                    return None
        return None

    def batch_rewrite_lines(self, text_batch: List[str]) -> Optional[Dict[str, str]]:
        """批量同义改写，严格保留%s/%zu等格式符"""
        prompt = self._build_standard_prompt(text_batch)
        messages = [{"role": "user", "content": prompt}]
        result = self._send_request(messages)
        
        if not result:
            return None
        
        # 解析JSON结果，兼容LLM输出格式
        try:
            # 清理可能的markdown包裹，纯解析JSON
            result = result.strip().strip("```json").strip("```")
            return json.loads(result)
        except json.JSONDecodeError:
            logger.error(f"JSON解析失败，模型输出：{result}")
            return None

    @staticmethod
    def _build_standard_prompt(text_list: List[str]) -> str:
        """强约束提示词，100%满足你的改写要求"""
        line_list = "\n".join([f"{i+1}. {line}" for i, line in enumerate(text_list)])
        return f"""
任务：对以下英文日志文本做**同义改写**，严格遵守所有规则：
1. 必须完整保留所有C/C++格式符：%s、%d、%zu、%f等，不修改、不丢失，且顺序保持一致
2. 仅调整连接词、句式，保留核心词汇，语义完全不变
3. 双引号、转义字符完全保留
4. 输出**仅返回标准JSON字典**，无任何多余文字：key=原始行，value=改写行
5. 严格使用双引号，禁止单引号，禁止markdown

待改写文本：
{line_list}
"""

# ====================== 3. 通用文件处理器（可复用资产） ======================
class FileTextProcessor:
    """批量文件读取、行去重、分块、格式符校验"""
    def __init__(self, config: ProcessConfig):
        self.config = config
        self.format_re = re.compile(r"%[sdzufl]")  # 匹配所有C格式占位符

    def load_all_lines(self, file_paths: List[str]) -> List[str]:
        """读取多个文件，合并所有非空行"""
        all_lines = []
        for fp in file_paths:
            try:
                with open(fp, "r", encoding=self.config.file_encoding) as f:
                    lines = [line.strip() for line in f if line.strip()]
                    all_lines += lines
                    logger.info(f"文件{fp}读取完成，行数：{len(lines)}")
            except Exception as e:
                logger.error(f"文件{fp}读取失败：{str(e)}")
        return self._deduplicate(all_lines)

    def _deduplicate(self, lines: List[str]) -> List[str]:
        """行去重，减少API调用成本"""
        seen, unique = set(), []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique.append(line)
        logger.info(f"去重前：{len(lines)}行，去重后：{len(unique)}行")
        return unique

    def split_batches(self, lines: List[str]) -> List[List[str]]:
        """按批次拆分，适配批量调用"""
        return [lines[i:i+self.config.batch_size] for i in range(0, len(lines), self.config.batch_size)]

    def check_format_consistent(self, orig: str, new: str) -> bool:
        """校验格式符数量、类型完全一致"""
        return self.format_re.findall(orig) == self.format_re.findall(new)

# ====================== 4. 并发调度器（高吞吐处理大文件） ======================
class BatchRewriteScheduler:
    """并发调度核心，支持多文件、几千行批量处理"""
    def __init__(self, llm: LLMChatClient, processor: FileTextProcessor, proc_cfg: ProcessConfig):
        self.llm = llm
        self.proc = processor
        self.cfg = proc_cfg
        self.result_map: Dict[str, str] = {}

    def execute(self, file_paths: List[str]) -> Tuple[Dict[str, str], List[str]]:
        """主执行入口"""
        # 1. 加载+去重+分块
        lines = self.proc.load_all_lines(file_paths)
        if not lines:
            return {}, []
        batches = self.proc.split_batches(lines)
        logger.info(f"总批次：{len(batches)}，并发数：{self.cfg.max_workers}")

        # 2. 线程池并发调用
        failed_lines = []
        with ThreadPoolExecutor(max_workers=self.cfg.max_workers) as pool:
            future_map = {pool.submit(self.llm.batch_rewrite_lines, b): b for b in batches}
            
            for future in as_completed(future_map):
                batch = future_map[future]
                try:
                    res = future.result()
                    if res:
                        success_batch, failed_batch = self._process_batch_result(res)
                        self.result_map.update(success_batch)
                        failed_lines += failed_batch
                        logger.info(f"Batch processed: {len(success_batch)} success, {len(failed_batch)} failed")
                    else:
                        failed_lines += batch
                except Exception as e:
                    logger.error(f"Batch processing error: {str(e)}")
                    failed_lines += batch

        logger.info(f"Task complete: {len(self.result_map)} success, {len(failed_lines)} failed")
        return self.result_map, failed_lines

    def _process_batch_result(self, res: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
        """Individual line validation"""
        success = {}
        failed = []
        for k, v in res.items():
            if self.proc.check_format_consistent(k, v):
                success[k] = v
            else:
                logger.error(f"Format mismatch: {k} → {v}")
                failed.append(k)
        return success, failed

# ====================== 5. 输出转换器（满足你的最终格式要求） ======================
class ResultConverter:
    """转换为标准JSON字符串 + Python r字符串字典"""
    @staticmethod
    def to_json_str(data: Dict[str, str]) -> str:
        return json.dumps(data, ensure_ascii=False, indent=4)

    @staticmethod
    def to_python_r_dict(data: Dict[str, str]) -> Dict[str, str]:
        """生成Python原生r字符串，处理转义字符"""
        return {rf"{k}": rf"{v}" for k, v in data.items()}

# ====================== 主运行函数 ======================
def run_rewrite_task(file_paths: List[str], llm_cfg: Optional[LLMConfig] = None):
    # 初始化配置
    if llm_cfg is None:
        llm_cfg = LLMConfig() # 默认使用 DeepSeek
    proc_cfg = ProcessConfig()
    
    # 初始化组件
    llm_client = LLMChatClient(llm_cfg)
    processor = FileTextProcessor(proc_cfg)
    scheduler = BatchRewriteScheduler(llm_client, processor, proc_cfg)
    converter = ResultConverter()
    
    # 执行批量改写
    result_dict, failed = scheduler.execute(file_paths)
    
    # 输出最终结果
    json_str = converter.to_json_str(result_dict)
    python_r_dict = converter.to_python_r_dict(result_dict)
    
    # 打印结果
    print("="*60)
    print("Standard JSON string output:")
    print(json_str)
    print("="*60)
    print("Python r-string dictionary output (can be directly embedded in code):")
    print(python_r_dict)
    
    # 保存结果
    with open("LLM_rewrite_result.json", "w", encoding="utf-8") as f:
        f.write(json_str)
    logger.info("Result saved to LLM_rewrite_result.json")
    
    return python_r_dict, failed

# ====================== 使用示例 ======================
if __name__ == "__main__":
    # 配置 1: DeepSeek (云端)
    deepseek_config = LLMConfig(
        api_key="sk-898f757847b0461da3d48***********",
        base_url="https://api.deepseek.com/v1/chat/completions",
        model="deepseek-chat"
    )

    # 配置 2: 局域网本地 LLM (Qwen)
    local_llm_config = LLMConfig(
        api_key=None,  # 本地 LLM 无需 API Key
        base_url="http://192.168.5.85:8000/v1/chat/completions",
        model="qwen3.5:27b"
    )

    # 待处理文件
    TARGET_FILES = [
        "test_log_1.txt",
        "test_log_2.txt"
    ]

    # 选择使用的配置（切换此处即可）
    # current_config = deepseek_config
    current_config = local_llm_config

    final_r_dict, fail_lines = run_rewrite_task(TARGET_FILES, current_config)
