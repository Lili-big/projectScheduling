import { useState } from "react";

import { importGirderProgressActuals } from "../../api/girderPlanningApi";
import type {
  GirderExecutionActual,
  GirderProgressImportPreview,
  PassageActual,
  YardInventoryActual,
} from "../../contracts";

export function GirderProgressEditor({
  yardActuals,
  executionActuals,
  machineActuals,
  passageActuals,
  onImported,
}: {
  yardActuals: YardInventoryActual[];
  executionActuals: GirderExecutionActual[];
  machineActuals?: Array<{ erection_machine_id: string }>;
  passageActuals: PassageActual[];
  onImported?: (preview: GirderProgressImportPreview) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function importFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      const payload = new FormData();
      payload.append("file", file);
      const preview = await importGirderProgressActuals(payload);
      onImported?.(preview);
      if (preview.diagnostics.some((item) => item.level === "error")) {
        setError("文件已解析，但存在错误行；错误行未进入当前实绩。请修正后重新导入。");
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "架梁实绩导入失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="girder-card">
      <div className="girder-card-heading">
        <h3>架梁实绩</h3>
        <label className="girder-file-button">
          {busy ? "解析中…" : "导入实绩 Excel"}
          <input type="file" accept=".xlsx,.xlsm,.csv,.tsv" disabled={busy} onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void importFile(file);
            event.currentTarget.value = "";
          }} />
        </label>
      </div>
      {error && <div className="notice danger">{error}</div>}
      <div className="girder-version-strip">
        <span>梁场库存记录：{yardActuals.length}</span>
        <span>架梁任务实绩：{executionActuals.length}</span>
        <span>架桥机状态：{machineActuals?.length ?? 0}</span>
        <span>通行状态：{passageActuals.length}</span>
      </div>
    </section>
  );
}
