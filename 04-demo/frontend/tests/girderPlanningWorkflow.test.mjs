import assert from "node:assert/strict";
import test from "node:test";

import {
  createDefaultGirderPlanningConfig,
  girderConfigFingerprint,
  isGirderResultCurrent,
  withGirderPlanningConfig,
} from "../src/features/girderPlanning/adapter.ts";

test("架梁配置默认关闭且输入变化会产生新指纹", () => {
  const config = createDefaultGirderPlanningConfig("2026-01-01");
  assert.equal(config.enabled, false);
  assert.equal(config.parameters.post_erection_buffer_confirmed, false);
  assert.notEqual(girderConfigFingerprint(config), girderConfigFingerprint({ ...config, enabled: true }));
});

test("架梁配置写回场景且旧结果按输入指纹失效", () => {
  const scenario = { project: { start_date: "2026-01-01" } };
  const config = { ...createDefaultGirderPlanningConfig("2026-01-01"), enabled: true };
  const next = withGirderPlanningConfig(scenario, config);
  assert.equal(next.girder_planning.enabled, true);
  assert.equal(isGirderResultCurrent({ input_fingerprint: "fp" }, "fp"), true);
  assert.equal(isGirderResultCurrent({ input_fingerprint: "old" }, "fp"), false);
});
