"""Автомат состояний сигналов перекрёстка — ядро безопасности этапа 2.

Состояния и единственно допустимые переходы (таблица `ALLOWED_TRANSITIONS`):

    STARTUP_ALL_RED ──(startup_all_red_sec)──▶ GREEN(p)
    GREEN(p) ──(≥ min_green; решение контроллера или max_green)──▶ YELLOW(p)
    YELLOW(p) ──(ровно yellow_sec)──▶ ALL_RED
    ALL_RED ──(ровно all_red_clearance_sec)──▶ GREEN(q)
    любое ──(нарушение безопасности / ошибка контроллера)──▶ FAULT
    FAULT ──(1 тик, все красные)──▶ STARTUP_ALL_RED  (перезапуск)

Сигналы групп:
- STARTUP_ALL_RED, ALL_RED, FAULT — все красные;
- GREEN(p)  — группы фазы p зелёные, остальные красные;
- YELLOW(p) — группы фазы p жёлтые, остальные красные.

Отклонения от минимальной схемы ТЗ (задокументированы):
- FAULT длится один тик и всегда ведёт в STARTUP_ALL_RED, который сам держит все
  красные не меньше startup_all_red_sec — это и есть «ALL_RED (restart)» из ТЗ.
- Группа, входящая и в текущую, и в следующую фазу, всё равно проходит через
  жёлтый и all-red (без «перекрытий» overlap) — проще и заведомо безопасно.
- max_green — жёсткий предел зелёного в обоих режимах: даже если других заявок
  нет, по max_green фаза уходит в жёлтый. Так инвариант
  `min_green ≤ длительность зелёного ≤ max_green` выполняется всегда и проверяется
  тестами без оговорок.

Инвариант безопасности: в любой момент две группы из матрицы конфликтов не могут
обе показывать разрешающий (зелёный или жёлтый) сигнал. Обеспечивается двумя
независимыми слоями:
 1. Структурно: зелёный включается только из ALL_RED (всё красное) и только для
    групп одной фазы; валидация профиля запрещает фазы с конфликтующими группами.
 2. Аппаратно-подобный предохранитель `_apply_signals`: перед ЛЮБОЙ сменой
    сигналов новое состояние проверяется по матрице конфликтов. Если оно
    нарушает инвариант (например, профиль собран в обход валидации), сигналы не
    применяются, автомат уходит в FAULT (все красные), счётчик
    `blocked_violations` увеличивается. Конфликтующее состояние физически не
    выставляется ни на один тик.

Всё время — в целых тиках модели (dt = 0.1 с), поэтому тайминги соблюдаются точно.
"""
from __future__ import annotations

from enum import Enum

from app.simulation.controllers import BaseController, DemandView
from app.simulation.models import SIM_DT, IntersectionProfile


class SignalState(str, Enum):
    STARTUP_ALL_RED = "STARTUP_ALL_RED"
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ALL_RED = "ALL_RED"
    FAULT = "FAULT"


ALLOWED_TRANSITIONS: dict[SignalState, set[SignalState]] = {
    SignalState.STARTUP_ALL_RED: {SignalState.GREEN, SignalState.FAULT},
    SignalState.GREEN: {SignalState.YELLOW, SignalState.FAULT},
    SignalState.YELLOW: {SignalState.ALL_RED, SignalState.FAULT},
    SignalState.ALL_RED: {SignalState.GREEN, SignalState.FAULT},
    SignalState.FAULT: {SignalState.STARTUP_ALL_RED, SignalState.FAULT},
}

RED, YELLOW, GREEN = "red", "yellow", "green"
PERMISSIVE = {GREEN, YELLOW}


class SafetyViolation(RuntimeError):
    pass


class SignalMachine:
    def __init__(self, profile: IntersectionProfile, controller: BaseController, dt: float = SIM_DT):
        self.profile = profile
        self.controller = controller
        self.dt = dt
        self.groups = [g.id for g in profile.signal_groups]
        self.conflicts = profile.conflict_pairs()

        self.tick = 0
        self.state = SignalState.STARTUP_ALL_RED
        self.state_entered_tick = 0
        self.phase: str | None = None  # текущая (в GREEN/YELLOW) или последняя зелёная фаза
        self.next_phase: str | None = None
        self.last_end_reason: str = ""
        self.signals: dict[str, str] = {g: RED for g in self.groups}

        self.blocked_violations = 0
        self.fault_count = 0
        self.fault_reasons: list[str] = []
        # журнал переходов: {tick, t, from, to, phase, reason, signals}
        self.transitions: list[dict] = []
        # завершённые зелёные: {phase_id, start_sec, end_sec, duration_sec, reason, mode}
        self.green_log: list[dict] = []
        self._green_mode = controller.mode
        self._log_transition(None, SignalState.STARTUP_ALL_RED, "startup")

    # --- вспомогательные ---

    def ticks(self, sec: float) -> int:
        return int(round(sec / self.dt))

    @property
    def elapsed_ticks(self) -> int:
        return self.tick - self.state_entered_tick

    @property
    def elapsed_sec(self) -> float:
        return self.elapsed_ticks * self.dt

    def min_green_sec(self, phase_id: str) -> float:
        return self.profile.min_green(phase_id)

    def max_green_sec(self, phase_id: str) -> float:
        return self.profile.max_green(phase_id)

    def set_controller(self, controller: BaseController) -> None:
        """Смена режима на лету: текущий интервал не прерывается, новые правила
        применяются со следующего решения (тайминги автомата не меняются)."""
        self.controller = controller

    def permissive_groups(self) -> set[str]:
        return {g for g, c in self.signals.items() if c in PERMISSIVE}

    def is_safe(self, signals: dict[str, str] | None = None) -> bool:
        sig = self.signals if signals is None else signals
        perm = {g for g, c in sig.items() if c in PERMISSIVE}
        return not any(pair <= perm for pair in self.conflicts)

    # --- предохранитель ---

    def _apply_signals(self, new_signals: dict[str, str]) -> None:
        if not self.is_safe(new_signals):
            self.blocked_violations += 1
            bad = sorted(
                "/".join(sorted(pair))
                for pair in self.conflicts
                if pair <= {g for g, c in new_signals.items() if c in PERMISSIVE}
            )
            raise SafetyViolation(f"заблокировано конфликтующее состояние сигналов: {bad}")
        self.signals = new_signals

    def _signals_for(self, state: SignalState, phase: str | None) -> dict[str, str]:
        sig = {g: RED for g in self.groups}
        if state in (SignalState.GREEN, SignalState.YELLOW) and phase is not None:
            color = GREEN if state == SignalState.GREEN else YELLOW
            for g in self.profile.phase(phase).signal_groups:
                sig[g] = color
        return sig

    def _log_transition(self, frm: SignalState | None, to: SignalState, reason: str) -> None:
        self.transitions.append(
            {
                "tick": self.tick,
                "t": round(self.tick * self.dt, 3),
                "from": frm.value if frm else None,
                "to": to.value,
                "phase": self.phase if to in (SignalState.GREEN, SignalState.YELLOW) else None,
                "next_phase": self.next_phase,
                "reason": reason,
                "mode": self.controller.mode,
                "signals": dict(self.signals),
            }
        )

    def _enter(self, to: SignalState, reason: str, phase: str | None = None) -> None:
        frm = self.state
        if to not in ALLOWED_TRANSITIONS[frm]:
            raise SafetyViolation(f"недопустимый переход {frm.value} → {to.value}")
        if to == SignalState.GREEN:
            if frm not in (SignalState.ALL_RED, SignalState.STARTUP_ALL_RED):
                raise SafetyViolation("зелёный разрешён только после полного красного")
            if any(c != RED for c in self.signals.values()):
                raise SafetyViolation("перед зелёным не все сигналы красные")
            if phase is None:
                raise SafetyViolation("не задана фаза для зелёного")
            self.profile.phase(phase)  # KeyError/StopIteration → FAULT
        new_phase = phase if to == SignalState.GREEN else self.phase
        self._apply_signals(self._signals_for(to, new_phase))
        self.state = to
        self.phase = new_phase
        self.state_entered_tick = self.tick
        if to == SignalState.GREEN:
            self._green_mode = self.controller.mode
        self._log_transition(frm, to, reason)

    def _fault(self, reason: str) -> None:
        frm = self.state
        self.fault_count += 1
        self.fault_reasons.append(f"t={self.tick * self.dt:.1f}: {reason}")
        self.signals = {g: RED for g in self.groups}  # все красные — всегда безопасно
        self.state = SignalState.FAULT
        self.state_entered_tick = self.tick
        self.next_phase = None
        self._log_transition(frm, SignalState.FAULT, reason)

    # --- шаг ---

    def step(self, demand: DemandView) -> None:
        """Выставить сигналы на интервал [tick·dt, (tick+1)·dt) и продвинуть время.

        Решение принимается в начале интервала по спросу, измеренному в этот же
        момент; смена сигнала журналируется этим моментом, машины движутся под
        новыми сигналами весь интервал."""
        try:
            self._step_impl(demand)
        except Exception as exc:  # noqa: BLE001 — любая ошибка → безопасное состояние
            self._fault(str(exc) or exc.__class__.__name__)
        self.tick += 1

    def _step_impl(self, demand: DemandView) -> None:
        t = self.profile.timings
        s = self.state
        el = self.elapsed_ticks

        if s == SignalState.FAULT:
            self._enter(SignalState.STARTUP_ALL_RED, "restart_after_fault")
        elif s == SignalState.STARTUP_ALL_RED:
            if el >= self.ticks(t.startup_all_red_sec):
                first = self.controller.initial_phase(demand)
                self.next_phase = first
                self._enter(SignalState.GREEN, "startup_done", first)
        elif s == SignalState.GREEN:
            assert self.phase is not None
            if el < self.ticks(self.min_green_sec(self.phase)):
                return  # min_green: контроллер даже не спрашивается
            if el >= self.ticks(self.max_green_sec(self.phase)):
                nxt, _ = self.controller.choose_next(self, demand)
                self._end_green("max_out", nxt)
                return
            d = self.controller.decide(self, demand)
            if d.end:
                self._end_green(d.reason, d.next_phase)
        elif s == SignalState.YELLOW:
            if el >= self.ticks(t.yellow_sec):
                self._enter(SignalState.ALL_RED, "yellow_done")
        elif s == SignalState.ALL_RED:
            if el >= self.ticks(t.all_red_clearance_sec):
                self._enter(SignalState.GREEN, "clearance_done", self.next_phase)

    def _end_green(self, reason: str, next_phase: str | None) -> None:
        assert self.phase is not None
        if next_phase is None or next_phase == self.phase:
            raise SafetyViolation(f"контроллер вернул недопустимую следующую фазу: {next_phase}")
        if next_phase not in self.profile.allowed_next(self.phase):
            raise SafetyViolation(
                f"переход {self.phase} → {next_phase} не разрешён профилем"
            )
        start = self.state_entered_tick * self.dt
        self.green_log.append(
            {
                "phase_id": self.phase,
                "start_sec": round(start, 3),
                "end_sec": round(self.tick * self.dt, 3),
                "duration_sec": round(self.elapsed_ticks * self.dt, 3),
                "reason": reason,
                "mode": self._green_mode if self._green_mode == self.controller.mode else "mixed",
                "next_phase": next_phase,
            }
        )
        self.next_phase = next_phase
        self.last_end_reason = reason
        self._enter(SignalState.YELLOW, reason)

    # --- для интерфейса ---

    def remaining_sec(self, demand: DemandView) -> float | None:
        """Оставшееся время текущего интервала. Для GREEN в адаптивном режиме —
        расчётное (может измениться с приходом новых машин)."""
        t = self.profile.timings
        s = self.state
        if s == SignalState.GREEN and self.phase is not None:
            try:
                return round(self.controller.estimate_remaining_sec(self, demand), 1)
            except Exception:  # noqa: BLE001
                return None
        total = {
            SignalState.STARTUP_ALL_RED: t.startup_all_red_sec,
            SignalState.YELLOW: t.yellow_sec,
            SignalState.ALL_RED: t.all_red_clearance_sec,
            SignalState.FAULT: self.dt,
        }[s]
        return round(max(0.0, total - self.elapsed_sec), 1)
