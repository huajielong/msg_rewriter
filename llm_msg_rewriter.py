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
    api_key: Optional[str] = "sk-7263afe43d0644c8adc30***********"
    base_url: str = "https://api.deepseek.com/v1/chat/completions"
    model: str = "deepseek-chat"
    temperature: float = 0.1  # 低温度保证改写精准，不跑偏
    top_p: float = 0.3
    repetition_penalty: float = 1.0
    max_tokens: int = 5120  # DeepSeek 最大输出 token 为 5120
    timeout: int = 180
    max_retry: int = 5  # 接口失败自动重试

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
                if resp.status_code != 200:
                    logger.warning(f"LLM请求失败 (Status {resp.status_code})，响应内容：{resp.text}")
                
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.warning(f"LLM请求失败，第{retry+1}次重试：{str(e)}")
                if retry == self.config.max_retry - 1:
                    logger.error(f"最终请求失败：{str(e)}")
                    return None
        return None

    def _preprocess_json(self, s: str) -> str:
        """预处理 JSON 字符串，修复 LLM 常见的语法错误"""
        if not s:
            return s
        
        # 1. 修复非法的单引号转义 \'。
        # JSON 不支持 \'，但支持 \\' (即转义后的反斜杠加单引号)。
        # 我们将 \' 替换为 \\'，这样 json.loads 既能解析成功，又能保留原始文本中的 \'。
        s = s.replace(r"\'", r"\\'")
        
        # 2. 移除可能的尾随逗号 (例如 {"a": 1,})
        s = re.sub(r',\s*([\]}])', r'\1', s)
        return s.strip()

    def _extract_json(self, s: str) -> Optional[Dict]:
        """从杂乱字符串中提取第一个合法的 JSON 对象"""
        # 尝试所有可能的 { 起始位置
        for i in range(len(s)):
            if s[i] == '{':
                # 尝试从该位置开始解析
                try:
                    # 使用 raw_decode 提取第一个完整的 JSON 对象
                    decoder = json.JSONDecoder()
                    obj, end_idx = decoder.raw_decode(s[i:])
                    return obj
                except json.JSONDecodeError:
                    continue
        return None

    def _log_failure(self, text_batch: List[str], error: str, raw_output: str):
        """记录解析失败的批次原始文本，仅包含行内容，批次间空行区分"""
        log_file = "rewrite_failures.log"
        with open(log_file, "a", encoding="utf-8") as f:
            for line in text_batch:
                f.write(line + "\n")
            f.write("\n") # 批次间空行

    def batch_rewrite_lines(self, text_batch: List[str]) -> Optional[Dict[str, str]]:
        """批量同义改写，严格保留%s/%zu等格式符"""
        prompt = self._build_standard_prompt(text_batch)
        messages = [{"role": "user", "content": prompt}]
        result = self._send_request(messages)
        
        if not result:
            self._log_failure(text_batch, "API Request Failed (No Result)", "N/A")
            return None
        
        # 1. 过滤掉 <think>...</think> 标签内容（适配 DeepSeek-R1 等模型）
        result_no_think = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()
        
        # 2. 先进行通用的文本预处理（修复转义等）
        preprocessed_result = self._preprocess_json(result_no_think)
        
        # 2. 尝试提取 JSON
        try:
            # 策略 A: 直接解析
            return json.loads(preprocessed_result)
        except json.JSONDecodeError as e:
            # 策略 B: 从杂乱文本中寻找合法的 JSON 块
            brace_indices = [m.start() for m in re.finditer('{', preprocessed_result)]
            for idx in reversed(brace_indices):
                try:
                    decoder = json.JSONDecoder()
                    obj, _ = decoder.raw_decode(preprocessed_result[idx:])
                    if isinstance(obj, dict) and len(obj) > 0:
                        return obj
                except (json.JSONDecodeError, ValueError):
                    continue
            
            # 策略 C: 激进清理后提取
            clean_result = re.sub(r"```(?:json)?\s*(.*?)\s*```", r"\1", preprocessed_result, flags=re.DOTALL)
            if clean_result != preprocessed_result:
                res = self.batch_rewrite_lines_from_clean(clean_result)
                if res: return res
            
            # 记录失败详情
            self._log_failure(text_batch, str(e), result)
            logger.error(f"JSON解析最终失败，详情已记录至 rewrite_failures.log")
            return None

    def batch_rewrite_lines_from_clean(self, clean_text: str) -> Optional[Dict[str, str]]:
        """从清洗后的文本中再次尝试解析"""
        try:
            return json.loads(clean_text)
        except json.JSONDecodeError:
            # 重复一次策略 B 的逻辑
            brace_indices = [m.start() for m in re.finditer('{', clean_text)]
            for idx in reversed(brace_indices):
                try:
                    decoder = json.JSONDecoder()
                    obj, _ = decoder.raw_decode(clean_text[idx:])
                    if isinstance(obj, dict): return obj
                except: continue
        return None

    @staticmethod
    def _build_standard_prompt(text_list: List[str]) -> str:
        """Strongly constrained prompt in English to prevent character loss and Chinese output."""
        line_list = "\n".join([f"{i+1}. {line}" for i, line in enumerate(text_list)])
        return f"""
Task: Perform synonym rewriting for the following English log messages.

Rules (Must be strictly followed):
1. **Preserve All Characters**: You MUST preserve every single character from the original message that is not part of the synonym change. This includes all leading/trailing quotation marks ("), periods, spaces, and punctuation. If the original message is enclosed in quotes, the rewritten message MUST also be enclosed in quotes.
2. **Keep Format Specifiers**: You must preserve all C/C++ format specifiers (e.g., %s, %d, %zu, %f) exactly. Do not modify, remove, or change their order.
3. **Language Consistency**: The output MUST be in **English**. Do not translate to Chinese or any other language.
4. **Semantic Integrity**: Only adjust sentence structures or conjunctions. Keep core technical terms unchanged to ensure 100% semantic consistency.
5. **JSON Output Only**: 
   - Return ONLY a standard JSON dictionary.
   - Keys must be the EXACT original lines (including any quotes), and values must be the rewritten lines (including any quotes).
   - Use double quotes for JSON keys and values. Escape internal double quotes with a backslash (\\").
   - Do NOT escape single quotes (do not use \\').

Input Messages:
{line_list}

Example Output:
{{
  "\\"original message with %s\\"": "\\"rewritten message with %s\\"",
  "\\"original message for \\'kernel undefined\\' error.\\"": "\\"rewritten message for \\'kernel undefined\\' error.\\"",
  "regular message": "rewritten message"
}}

Output the JSON directly:
"""

# ====================== 3. 通用文件处理器（可复用资产） ======================
class FileTextProcessor:
    """批量文件读取、行去重、分块、格式符校验"""
    def __init__(self, config: ProcessConfig):
        self.config = config
        self.format_re = re.compile(r"%[sdzufl]")  # 匹配所有C格式占位符

    def load_all_lines(self, file_paths: List[str]) -> List[str]:
        """读取多个文件，合并所有非空行，并过滤掉单单词行"""
        all_lines = []
        for fp in file_paths:
            try:
                with open(fp, "r", encoding=self.config.file_encoding) as f:
                    # 过滤逻辑：1. 非空 2. 单词数 > 1
                    lines = []
                    for line in f:
                        clean_line = line.strip()
                        if not clean_line:
                            continue
                        
                        # 判定是否为单单词：去掉首尾引号后，检查是否有空格
                        # 例如 "gmnodes" -> gmnodes (无空格，跳过)
                        # 例如 "bad cast" -> bad cast (有空格，保留)
                        content = clean_line.strip('"').strip("'").strip()
                        if " " not in content:
                            continue
                            
                        lines.append(clean_line)
                    
                    all_lines += lines
                    logger.info(f"文件{fp}读取完成，有效行数：{len(lines)}")
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
        api_key="sk-7263afe43d0644c8adc30***********",
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
        # "test_log_2.txt"
    ]

    # 选择使用的配置（切换此处即可）
    current_config = deepseek_config
    # current_config = local_llm_config

    final_r_dict, fail_lines = run_rewrite_task(TARGET_FILES, current_config)
