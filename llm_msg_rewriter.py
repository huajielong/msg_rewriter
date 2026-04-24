import json
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import requests
from json_repair import repair_json

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
    timeout: int = 120
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
        
        # 2. 预处理：修复 LLM 偶尔在 JSON 字符串内部末尾多加的逗号
        # 例如将 "rewritten text," 修复为 "rewritten text"
        # 逻辑：匹配引号前面的逗号，且该引号后面紧跟着换行、逗号或 JSON 结束符
        result_no_think = re.sub(r'([^\\]),"(\s*[,\}\n])', r'\1"\2', result_no_think)
        
        # 3. 使用 json_repair 自动修复并解析 JSON
        try:
            # repair_json() 能处理 Markdown 代码块、缺失括号、非标准转义等多种错误
            repaired_json = repair_json(result_no_think)
            parsed_result = json.loads(repaired_json)
            
            if isinstance(parsed_result, dict) and len(parsed_result) > 0:
                return parsed_result
            
            logger.warning(f"JSON 解析成功但格式不符合预期（非字典或为空）")
        except Exception as e:
            # 记录失败详情
            self._log_failure(text_batch, str(e), result)
            logger.error(f"JSON解析最终失败，详情已记录至 rewrite_failures.log")
            
        return None

    @staticmethod
    def _build_standard_prompt(text_list: List[str]) -> str:
        """Strongly constrained prompt in English to prevent character loss and Chinese output."""
        line_list = "\n".join([f"{i+1}. {line}" for i, line in enumerate(text_list)])
        return f"""
Task: Perform synonym rewriting for the following English log messages.

Rules (Must be strictly followed):

1. **Preserve All Characters**: You MUST preserve all punctuation, spaces, leading/trailing quotation marks ("), and C/C++ format specifier characters from the original text. Characters involved in synonym replacement, word addition/deletion, article/pronoun adjustment and sentence structure fine-tuning are excluded from this preservation rule. If the original message is enclosed in quotes, the rewritten message MUST also be enclosed in quotes.
2. **Keep Format Specifiers**: You must preserve all C/C++ format specifiers (e.g., %s, %d, %zu, %f) exactly. Do not modify, remove, or change their order.
3. **Language Consistency**: The output MUST be in **English**. Do not translate to Chinese or any other language.
4. **Semantic Integrity**: Synonym replacement is permitted. You may fine-tune sentence structures, word order, and adjust connecting words. Core technical terms must remain unchanged to guarantee 100% semantic consistency.
5. **Word Modification Scope**: Articles (a, an, the) and pronouns can be appropriately added or removed. You are only allowed to add, delete or replace connecting & transitional words, adjust sentence structures and word order, and perform authorized synonym replacement on non-core common words, without altering the original overall meaning.
6. **Necessary Text Difference**: You MUST ensure that there are slight differences between the original text and the rewritten text. The result is strictly forbidden to be completely identical to the original content.
7. **JSON Output Only**:
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
        self.format_re = re.compile(r'%[-+ #0]*(\d+|\*)?(\.(\d+|\*))?([hlLjzt]|ll|hh)?[diufFeEgGxXoscpaAn]')  # 匹配所有C/C++格式占位符

    def load_all_lines(self, file_paths: List[str]) -> List[str]:
        """读取多个文件，合并所有非空行，并过滤掉单单词行"""
        all_lines = []
        for fp in file_paths:
            try:
                with open(fp, "r", encoding=self.config.file_encoding) as f:
                    # 过滤逻辑：1. 非空 2. 单词数 > 2
                    lines = []
                    for line in f:
                        clean_line = line.strip()
                        if not clean_line:
                            continue

                        content = clean_line.strip('"').strip("'").strip()                        
                        # 先去除 C 格式占位符 (如 %s, %d)，并去空格避免其占用的字母被误判为单词
                        content = self.format_re.sub(" ", content).strip()
                        
                        # 判定是否为单单词：使用正则匹配所有单词，若单词数 <= 2 则跳过
                        # 这样可以处理多个空格、制表符等情况
                        reg = r'[a-zA-Z]+(?:[_:\-\.>a-zA-Z]+)*'
                        if len(re.findall(reg, content)) <= 2:
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
        api_key="sk-2a334db655c742d68ad71af0a42d1eb6",
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
