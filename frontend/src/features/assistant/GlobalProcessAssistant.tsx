import { Bot, Loader2, Sparkles, X } from "lucide-react";
import { useState } from "react";
import type { ProcessNlResponse } from "../../types/scheduler";

export function GlobalProcessAssistant({
  onApplyProcessNaturalLanguage,
  applyingProcessText,
}: {
  onApplyProcessNaturalLanguage: (prompt: string) => Promise<ProcessNlResponse | null>;
  applyingProcessText: boolean;
}) {
  const [processPrompt, setProcessPrompt] = useState("");
  const [processNlResult, setProcessNlResult] = useState<ProcessNlResponse | null>(null);
  const [assistantOpen, setAssistantOpen] = useState(true);

  async function submitProcessPrompt() {
    const prompt = processPrompt.trim();
    if (!prompt || applyingProcessText) return;
    const result = await onApplyProcessNaturalLanguage(prompt);
    if (result) setProcessNlResult(result);
  }

  function useAssistantExample(prompt: string) {
    setProcessPrompt(prompt);
    setAssistantOpen(true);
  }

  return assistantOpen ? (
    <aside className="nl-process-panel" aria-label="全局 AI 操作助手">
      <div className="nl-process-title">
        <div className="nl-process-heading">
          <span className="assistant-mark"><Bot size={16} /></span>
          <div>
            <strong>AI 操作助手</strong>
            <span>自然语言录入工艺和工效</span>
          </div>
        </div>
        <button className="icon-button" type="button" aria-label="收起 AI 操作助手" onClick={() => setAssistantOpen(false)}>
          <X size={16} />
        </button>
      </div>
      <textarea
        value={processPrompt}
        onChange={(event) => setProcessPrompt(event.target.value)}
        placeholder="例如：左幅的3#墩和4#墩的桩基工艺设置成人工挖孔。"
      />
      <div className="assistant-examples" aria-label="快捷示例">
        <button type="button" onClick={() => useAssistantExample("桩基默认采用旋挖钻施工，其中1#墩-1桩基、1#墩-2桩基采用人工挖孔桩。")}>
          默认旋挖
        </button>
        <button type="button" onClick={() => useAssistantExample("渠溪河大桥连续梁主墩使用爬模施工。")}>
          主墩爬模
        </button>
        <button type="button" onClick={() => useAssistantExample("左幅的3#墩和4#墩的桩基工艺设置成人工挖孔。")}>
          指定墩位
        </button>
      </div>
      <button className="primary assistant-submit" disabled={!processPrompt.trim() || applyingProcessText} onClick={submitProcessPrompt}>
        {applyingProcessText ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
        让助手执行
      </button>
      {processNlResult && (
        <div className="nl-process-result">
          {processNlResult.changes.map((change, index) => (
            <span key={`${change.action}-${index}`}>{change.message}</span>
          ))}
          {processNlResult.warnings.map((warning, index) => (
            <span className="warn" key={`${warning}-${index}`}>{warning}</span>
          ))}
        </div>
      )}
    </aside>
  ) : (
    <button className="assistant-launcher" type="button" aria-label="打开 AI 操作助手" onClick={() => setAssistantOpen(true)}>
      <Bot size={18} />
      <span>AI 助手</span>
    </button>
  );
}
