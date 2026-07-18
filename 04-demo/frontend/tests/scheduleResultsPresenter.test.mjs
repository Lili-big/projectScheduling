import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import ts from "typescript";

const root = resolve(import.meta.dirname, "..");

function toDataUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

function transpile(path) {
  return ts.transpileModule(readFileSync(path, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
    fileName: path,
  }).outputText;
}

async function loadPresenter() {
  const constantsUrl = toDataUrl(transpile(resolve(root, "src/domain/constants.ts")));
  const labelsUrl = toDataUrl(transpile(resolve(root, "src/domain/labels.ts")));
  const resourcesUrl = toDataUrl(
    transpile(resolve(root, "src/domain/resources.ts"))
      .replaceAll('from "./constants"', `from "${constantsUrl}"`),
  );
  const source = transpile(resolve(root, "src/features/scheduleResults/presenter.ts"))
    .replace('from "../../domain/labels"', `from "${labelsUrl}"`)
    .replace('from "../../domain/resources"', `from "${resourcesUrl}"`);
  return import(toDataUrl(source));
}

const pools = [
  {
    id: "shared-pool",
    type: "shared-type",
    label: "共享资源",
    resource_mode: "LIMITED",
    scope_mode: "PROJECT_SHARED",
    quantity: 1,
    max_quantity: 2,
    authorized_workpoint_ids: ["WP-A", "WP-B"],
    workpoint_overrides: [],
    calendar_id: "continuous",
    enabled: true,
    compatible_process_ids: [],
  },
  {
    id: "exclusive-pool",
    type: "exclusive-type",
    label: "独享资源",
    resource_mode: "LIMITED",
    scope_mode: "WORKPOINT_EXCLUSIVE",
    quantity: 2,
    max_quantity: 4,
    authorized_workpoint_ids: ["WP-A"],
    workpoint_overrides: [{ workpoint_id: "WP-A", quantity: 3 }],
    calendar_id: "continuous",
    enabled: true,
    compatible_process_ids: [],
  },
];

function generated() {
  return {
    source_summary: {},
    validation: [],
    schedule_input: {
      project_name: "项目",
      start_date: "2026-01-01",
      precedence_links: [],
      milestones: [],
      execution_constraints: [],
      time_limit_seconds: 1,
      tasks: [
        { id: "task-a", bridge_id: "WP-A" },
        { id: "task-b", bridge_id: "WP-B" },
      ],
      resources: [
        {
          id: "resource-alpha",
          name: "共享一",
          type: "shared-type",
          pool_id: "shared-pool",
          enabled: true,
          calendar_id: "continuous",
          scope_mode: "PROJECT_SHARED",
          eligible_workpoint_ids: ["WP-A", "WP-B"],
          exclusive_workpoint_id: null,
        },
        {
          id: "opaque-resource",
          name: "独享一",
          type: "exclusive-type",
          pool_id: "exclusive-pool",
          enabled: true,
          calendar_id: "continuous",
          scope_mode: "WORKPOINT_EXCLUSIVE",
          eligible_workpoint_ids: ["WP-A"],
          exclusive_workpoint_id: "WP-A",
        },
      ],
    },
  };
}

function result() {
  return {
    resource_allocations: [
      { resource_id: "resource-alpha", task_id: "task-a" },
      { resource_id: "resource-alpha", task_id: "task-b" },
      { resource_id: "opaque-resource", task_id: "task-a" },
    ],
    stats: {
      recommended_resource_counts: [
        {
          resource_pool_id: "shared-pool",
          label: "共享资源",
          resource_type: "shared-type",
          recommended_quantity: 2,
          max_quantity: 2,
        },
        {
          resource_pool_id: "exclusive-pool::workpoint::WP-A",
          label: "独享资源",
          resource_type: "exclusive-type",
          recommended_quantity: 4,
          max_quantity: 4,
        },
      ],
      resource_scope_diagnostics: {
        rule_version: "workpoint-resource-scope/v1",
        project_shared_transfer_time_days: 0,
        groups: [
          {
            resource_pool_id: "shared-pool",
            source_pool_id: "shared-pool",
            label: "共享资源",
            resource_type: "shared-type",
            scope_mode: "PROJECT_SHARED",
            workpoint_id: null,
            eligible_workpoint_ids: ["WP-A", "WP-B"],
            inheritance_source: "global",
            current_quantity: 1,
            recommended_quantity: 2,
            max_quantity: 2,
          },
          {
            resource_pool_id: "exclusive-pool::workpoint::WP-A",
            source_pool_id: "exclusive-pool",
            label: "独享资源",
            resource_type: "exclusive-type",
            scope_mode: "WORKPOINT_EXCLUSIVE",
            workpoint_id: "WP-A",
            eligible_workpoint_ids: ["WP-A"],
            inheritance_source: "workpoint_override",
            current_quantity: 3,
            recommended_quantity: 4,
            max_quantity: 4,
          },
        ],
        allocations: [],
      },
    },
    objective_breakdown: {},
  };
}

test("result rows use explicit scope fields and authoritative workpoint names", async () => {
  const { buildResourceScopeResult, projectSharedTransferNotice } = await loadPresenter();
  const presentation = buildResourceScopeResult({
    generated: generated(),
    result: result(),
    resourcePools: pools,
    workpoints: [
      { workpoint_id: "WP-A", workpoint_name: "一号工点" },
      { workpoint_id: "WP-B", workpoint_name: "二号工点" },
    ],
  });

  assert.equal(presentation.showProjectSharedNotice, true);
  assert.equal(presentation.notice, projectSharedTransferNotice);
  assert.deepEqual(presentation.rows.map((row) => ({
    scope: row.scopeLabel,
    workpoints: row.workpointLabel,
    current: row.currentQuantity,
    recommended: row.recommendedQuantity,
  })), [
    { scope: "项目共享", workpoints: "一号工点、二号工点", current: 1, recommended: 2 },
    { scope: "工点独享", workpoints: "一号工点", current: 3, recommended: 4 },
  ]);
});

test("missing scope or authority stays generically unavailable and never parses resource ids", async () => {
  const { buildResourceScopeResult } = await loadPresenter();
  const payload = generated();
  payload.schedule_input.resources = [{
    id: "WP-A:shared-pool:1",
    name: "旧资源",
    type: "shared-type",
    pool_id: "shared-pool",
    enabled: true,
    calendar_id: "continuous",
    eligible_workpoint_ids: ["WP-A"],
  }];
  const presentation = buildResourceScopeResult({
    generated: payload,
    result: { ...result(), resource_allocations: [] },
    resourcePools: pools,
    workpoints: [],
  });

  assert.equal(presentation.rows[0].scopeLabel, "作用域不可用");
  assert.equal(presentation.rows[0].workpointLabel, "工点信息不可用");
  assert.doesNotMatch(presentation.rows[0].workpointLabel, /WP-A|shared-pool/);
});
