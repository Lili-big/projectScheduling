import { CalendarDays } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

export type DateRangePickerProps = {
  startDate: string;
  finishDate: string;
  minDate?: string;
  maxDate?: string;
  onChange: (range: { startDate: string; finishDate: string }) => void;
};

export function DateRangePicker({ startDate, finishDate, minDate, maxDate, onChange }: DateRangePickerProps) {
  const [open, setOpen] = useState(false);
  const [selectingFinish, setSelectingFinish] = useState(false);
  const [visibleMonth, setVisibleMonth] = useState(() => monthKey(startDate || minDate || todayDateValue()));
  const pickerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    setVisibleMonth(monthKey(startDate || minDate || todayDateValue()));
  }, [open, startDate, minDate]);

  useEffect(() => {
    if (!open) return;
    function handleDocumentPointerDown(event: MouseEvent) {
      if (!pickerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleDocumentPointerDown);
    return () => document.removeEventListener("mousedown", handleDocumentPointerDown);
  }, [open]);

  const calendarDays = useMemo(() => calendarDaysForMonth(visibleMonth), [visibleMonth]);
  const waitingForFinish = selectingFinish && Boolean(startDate) && !finishDate;
  const rangeLabel = startDate && finishDate ? `${startDate} - ${finishDate}` : startDate ? `${startDate} -` : "选择时间范围";
  const disablePreviousMonth = Boolean(minDate && compareDateValues(monthLastDate(addMonthsToMonthKey(visibleMonth, -1)), minDate) < 0);
  const disableNextMonth = Boolean(maxDate && compareDateValues(monthFirstDate(addMonthsToMonthKey(visibleMonth, 1)), maxDate) > 0);

  function handleDateClick(dateValue: string) {
    if (!startDate || !selectingFinish || finishDate) {
      onChange({ startDate: dateValue, finishDate: "" });
      setSelectingFinish(true);
      return;
    }
    if (compareDateValues(dateValue, startDate) <= 0) return;
    onChange({ startDate, finishDate: dateValue });
    setSelectingFinish(false);
    setOpen(false);
  }

  function clearRange() {
    onChange({ startDate: "", finishDate: "" });
    setSelectingFinish(false);
  }

  return (
    <div className="date-range-picker" ref={pickerRef}>
      <button className="date-range-trigger" type="button" onClick={() => setOpen((current) => !current)}>
        <CalendarDays size={15} />
        <span>{rangeLabel}</span>
      </button>
      {open && (
        <div className="date-range-popover">
          <div className="date-range-fields">
            <span><strong>开始</strong>{startDate || "-"}</span>
            <span><strong>完成</strong>{finishDate || "-"}</span>
          </div>
          <div className="date-range-monthbar">
            <button type="button" onClick={() => setVisibleMonth(addMonthsToMonthKey(visibleMonth, -1))} disabled={disablePreviousMonth}>‹</button>
            <strong>{formatMonthLabel(visibleMonth)}</strong>
            <button type="button" onClick={() => setVisibleMonth(addMonthsToMonthKey(visibleMonth, 1))} disabled={disableNextMonth}>›</button>
          </div>
          <div className="date-range-weekdays">
            {dateRangeWeekdays.map((weekday) => <span key={weekday}>{weekday}</span>)}
          </div>
          <div className="date-range-grid">
            {calendarDays.map((day) => {
              const beforeStart = waitingForFinish && compareDateValues(day.value, startDate) <= 0;
              const outsideBounds = Boolean(minDate && compareDateValues(day.value, minDate) < 0)
                || Boolean(maxDate && compareDateValues(day.value, maxDate) > 0);
              const selected = day.value === startDate || day.value === finishDate;
              const inRange = Boolean(startDate && finishDate)
                && compareDateValues(day.value, startDate) > 0
                && compareDateValues(day.value, finishDate) < 0;
              return (
                <button
                  className={`${day.inMonth ? "" : "muted"} ${selected ? "selected" : ""} ${inRange ? "in-range" : ""}`}
                  disabled={beforeStart || outsideBounds}
                  key={day.value}
                  onClick={() => handleDateClick(day.value)}
                  type="button"
                >
                  {Number(day.value.slice(-2))}
                </button>
              );
            })}
          </div>
          <div className="date-range-footer">
            <span>{waitingForFinish ? "选择完成日期" : "选择开始日期"}</span>
            <button type="button" onClick={clearRange}>清空</button>
          </div>
        </div>
      )}
    </div>
  );
}

const dateRangeWeekdays = ["一", "二", "三", "四", "五", "六", "日"];
type CalendarDay = { value: string; inMonth: boolean };

function todayDateValue(): string { return dateToInputValue(new Date()); }
function monthKey(value: string): string { return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.slice(0, 7) : todayDateValue().slice(0, 7); }
function formatMonthLabel(month: string): string { const [year, value] = month.split("-"); return `${year}年${Number(value)}月`; }
function monthFirstDate(month: string): string { return `${month}-01`; }
function compareDateValues(left: string, right: string): number { return left.localeCompare(right); }

function calendarDaysForMonth(month: string): CalendarDay[] {
  const first = parseDateValue(`${month}-01`) ?? new Date();
  const gridStart = addDays(first, -((first.getDay() + 6) % 7));
  return Array.from({ length: 42 }, (_, index) => {
    const value = dateToInputValue(addDays(gridStart, index));
    return { value, inMonth: value.startsWith(month) };
  });
}

function addMonthsToMonthKey(month: string, delta: number): string {
  const [year, value] = month.split("-").map(Number);
  return dateToInputValue(new Date(year, value - 1 + delta, 1)).slice(0, 7);
}

function monthLastDate(month: string): string {
  const [year, value] = month.split("-").map(Number);
  return dateToInputValue(new Date(year, value, 0));
}

function parseDateValue(value: string): Date | null {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : null;
}

function dateToInputValue(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}
