import {
  ArrowRight,
  FileCheck2,
  FileText,
  Files,
  Loader2,
  RefreshCw,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import type {
  AiParameterApplyRequest,
  AiParameterApplyResponse,
  AiParameterConflictGroup,
  AiParameterParseResponse,
  ScenarioInput,
} from "../../../types/scheduler";
import {
  aiParameterMaterialKindLabels,
  canApplyAiParameterSelection,
  formatAiParameterValue,
  isAiParameterConflictResolved,
  isDefaultAiParameterSelected,
} from "../../../domain/aiParameterAssistant";
import { ParameterCandidateList } from "./ParameterCandidateList";
import { ParameterConflictResolver } from "./ParameterConflictResolver";
import { ParameterSuggestionReview } from "./ParameterSuggestionReview";

const maxFiles = 10;

export function ParameterAssistantPanel({
  scenario,
  busy,
  onParse,
  onApply,
}: {
  scenario: ScenarioInput;
  busy: boolean;
  onParse: (payload: FormData) => Promise<AiParameterParseResponse | null>;
  onApply: (request: AiParameterApplyRequest) => Promise<AiParameterApplyResponse | null>;
}) {
  const [textInput, setTextInput] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [parseResult, setParseResult] = useState<AiParameterParseResponse | null>(null);
  const [applyResult, setApplyResult] = useState<AiParameterApplyResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [conflictResolutions, setConflictResolutions] = useState<Record<string, AiParameterConflictGroup>>({});
  const [localError, setLocalError] = useState<string | null>(null);

  const resolvedConflicts = useMemo(
    () => Object.values(conflictResolutions).filter(isAiParameterConflictResolved),
    [conflictResolutions],
  );
  const canApply = parseResult ? canApplyAiParameterSelection(selectedIds, resolvedConflicts) : false;
  const totalFileSize = files.reduce((sum, file) => sum + file.size, 0);

  async function submitParse() {
    const trimmedText = textInput.trim();
    if (busy) return;
    if (!trimmedText && files.length === 0) {
      setLocalError("请先上传项目资料，或粘贴需要解析的资料片段。");
      return;
    }
    setLocalError(null);
    setApplyResult(null);
    const payload = new FormData();
    payload.append("scenario", JSON.stringify(scenario));
    payload.append("assistant_mode", "parameter");
    if (trimmedText) payload.append("text_input", trimmedText);
    files.forEach((file, index) => payload.append(`file_${index}`, file, file.name));
    const result = await onParse(payload);
    if (!result) return;
    setParseResult(result);
    setSelectedIds(new Set(result.suggestions.filter(isDefaultAiParameterSelected).map((item) => item.suggestion_id)));
    setConflictResolutions({});
  }

  async function submitApply() {
    if (!parseResult || !canApply || busy) return;
    setLocalError(null);
    const manualValues = resolvedConflicts
      .filter((group) => group.resolution_status === "manual_value")
      .map((group) => ({
        conflict_group_id: group.conflict_group_id,
        parameter_key: group.parameter_key,
        value: group.manual_value,
      }));
    const result = await onApply({
      scenario,
      run_id: parseResult.run_id,
      selected_suggestion_ids: Array.from(selectedIds),
      conflict_resolutions: resolvedConflicts,
      manual_values: manualValues,
    });
    if (result) setApplyResult(result);
  }

  function updateSelected(id: string, checked: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function updateConflictResolution(resolution: AiParameterConflictGroup) {
    setConflictResolutions((current) => ({
      ...current,
      [resolution.conflict_group_id]: resolution,
    }));
  }

  function removeFile(index: number) {
    setFiles((current) => current.filter((_, fileIndex) => fileIndex !== index));
  }

  return (
    <div className="project-files-page" aria-label="项目文件">
      <section className="panel full project-files-hero">
        <div className="project-files-heading">
          <span className="project-files-icon"><Files size={22} /></span>
          <div>
            <h2>项目文件</h2>
            <p>集中上传施工组织设计、图纸、专项方案、资源计划等项目资料，解析后作为工艺、工效、资源和里程碑参数的输入依据。</p>
          </div>
        </div>
        <div className="project-files-flow" aria-label="项目资料处理流程">
          <span><b>1</b> 上传项目资料</span>
          <ArrowRight size={15} />
          <span><b>2</b> 系统解析参数</span>
          <ArrowRight size={15} />
          <span><b>3</b> 人工核验建议</span>
          <ArrowRight size={15} />
          <span><b>4</b> 应用到当前方案</span>
        </div>
      </section>

      <section className="panel full project-files-upload-card">
        <div className="project-files-section-title">
          <div>
            <strong>上传项目资料</strong>
            <span>单次最多上传 {maxFiles} 个文件；支持 Word、PDF、Excel、文本及常用图片格式。</span>
          </div>
          <span className="project-files-status"><FileCheck2 size={15} /> 解析结果需确认后生效</span>
        </div>

        <div className="project-files-input-grid">
          <label className="project-files-dropzone">
            <Upload size={26} />
            <strong>选择项目资料</strong>
            <span>施组、图纸、施工方案、资源计划、进度节点等</span>
            <em>DOC / DOCX / PDF / XLSX / 图片 / TXT</em>
            <input
              multiple
              type="file"
              accept=".txt,.md,.csv,.xlsx,.xlsm,.doc,.docx,.pdf,.png,.jpg,.jpeg,.webp,.bmp"
              onChange={(event) => {
                const selected = Array.from(event.target.files ?? []);
                setFiles((current) => [...current, ...selected].slice(0, maxFiles));
                event.currentTarget.value = "";
              }}
            />
          </label>

          <label className="project-files-text-input">
            <span>补充资料文本（选填）</span>
            <textarea
              value={textInput}
              onChange={(event) => setTextInput(event.target.value)}
              placeholder="可粘贴图纸说明、施组章节、资源计划或里程碑片段，系统会与已上传文件一并解析。"
            />
          </label>
        </div>

        {files.length > 0 && (
          <div className="ai-param-file-list project-files-selected">
            <div className="ai-param-file-summary">
              <strong>待解析文件</strong>
              <span>{files.length}/{maxFiles} 个 · {formatFileSize(totalFileSize)}</span>
            </div>
            <div className="project-files-file-grid">
              {files.map((file, index) => (
                <span key={`${file.name}-${file.lastModified}`}>
                  <FileText size={15} />
                  <span title={file.name}>{file.name}</span>
                  <em>{formatFileSize(file.size)}</em>
                  <button type="button" aria-label={`移除 ${file.name}`} onClick={() => removeFile(index)}>
                    <X size={13} />
                  </button>
                </span>
              ))}
            </div>
          </div>
        )}

        {localError && <div className="ai-param-error">{localError}</div>}

        <div className="project-files-actions">
          <span>解析不会直接修改当前方案；确认建议后才会写入后续排程参数。</span>
          <button
            className="primary"
            type="button"
            disabled={busy || (!textInput.trim() && files.length === 0)}
            onClick={submitParse}
          >
            {busy ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
            {busy ? "正在解析资料" : "解析项目资料"}
          </button>
        </div>
      </section>

      {parseResult && (
        <section className="panel full project-files-review-card">
          <div className="project-files-section-title">
            <div>
              <strong>参数解析结果</strong>
              <span>核验来源证据、建议值和冲突项，选择确认后再应用到当前方案。</span>
            </div>
            <div className="ai-param-run-summary">
              <span>{parseResult.suggestion_count} 条建议</span>
              <span>{parseResult.manual_completion_count} 待完善</span>
              <span>{formatExpiresAt(parseResult.expires_at)} 过期</span>
            </div>
          </div>

          <div className="ai-param-result">
            <div className="ai-param-materials">
              {parseResult.material_summaries.map((material) => (
                <span className={`is-${material.parse_status}`} key={material.material_id}>
                  <b>{aiParameterMaterialKindLabels[material.kind]}</b>
                  {material.file_name}
                  {material.error_message ? ` · ${material.error_message}` : ""}
                </span>
              ))}
            </div>

            {[...parseResult.errors, ...parseResult.warnings].length > 0 && (
              <div className="ai-param-validation">
                {[...parseResult.errors, ...parseResult.warnings].map((message, index) => (
                  <span key={`${message.message}-${index}`}>{message.message}</span>
                ))}
              </div>
            )}

            <ParameterSuggestionReview
              suggestions={parseResult.suggestions}
              materials={parseResult.material_summaries}
              selectedIds={selectedIds}
              onToggle={updateSelected}
            />
            <ParameterConflictResolver
              conflictGroups={parseResult.conflict_groups}
              suggestions={parseResult.suggestions}
              resolutions={conflictResolutions}
              onChange={updateConflictResolution}
            />
            <ParameterCandidateList
              candidates={parseResult.candidate_additions}
              materials={parseResult.material_summaries}
              selectedIds={selectedIds}
              onToggle={updateSelected}
            />

            <div className="ai-param-apply-bar">
              <span>已选 {selectedIds.size} 项，冲突处理 {resolvedConflicts.length} 项</span>
              <button className="primary" type="button" disabled={!canApply || busy} onClick={submitApply}>
                {busy ? <Loader2 className="spin" size={15} /> : <RefreshCw size={15} />}
                应用到当前方案
              </button>
            </div>
          </div>

          {applyResult && (
            <div className="ai-param-apply-result">
              <strong>应用摘要</strong>
              <span>已应用 {applyResult.application_summary.applied_count} 项</span>
              <span>跳过 {applyResult.application_summary.skipped_count} 项</span>
              <span>失败 {applyResult.application_summary.failed_count} 项</span>
              {applyResult.application_summary.manual_pending_count > 0 && (
                <span>待完善 {applyResult.application_summary.manual_pending_count} 项</span>
              )}
              {applyResult.application_summary.applied_items.slice(0, 5).map((item) => (
                <em key={item.suggestion_id}>
                  {item.parameter_key}：{formatAiParameterValue(item.old_value)} → {formatAiParameterValue(item.new_value)}
                </em>
              ))}
              {applyResult.application_summary.failed_items.map((item, index) => (
                <em className="is-error" key={`${item.message}-${index}`}>{item.message}</em>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function formatFileSize(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function formatExpiresAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}
