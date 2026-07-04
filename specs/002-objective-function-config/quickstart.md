# Quickstart: Objective Function Configuration

## Prerequisites

- Dependencies installed for backend and frontend.
- Local app can run through the standard FastAPI + built frontend path.

## Backend Validation

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

Expected:

- Existing scheduling tests still pass.
- New objective configuration tests prove default compatibility, disabled-term effective weight, invalid payload validation, and minimum-resource candidate refinement propagation.

## Frontend Validation

Run:

```powershell
npm --prefix frontend run build
```

Expected:

- TypeScript build succeeds.
- The full "模拟求解" page builds with objective controls.
- No "模拟求解-MVP" objective controls are added.

## Manual Browser Scenario

1. Open `http://127.0.0.1:8000/`.
2. Open the full "模拟求解" page.
3. Confirm "目标函数配置" appears in the "模拟参数" area.
4. Disable "普通工程均衡" and change another term's weight.
5. Click "固定资源条件下，推算最短工期".
6. Confirm the request completes and result metadata includes the changed effective objective weights.
7. Re-enable defaults with "恢复默认" and confirm the controls return to default weights.

## Scope Check

- Do not update `README.md`.
- Do not add local persistence for objective terms.
- Do not change resource-cost optimization's primary cost objective.
