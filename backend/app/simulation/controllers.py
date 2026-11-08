"""Контроллеры фаз: фиксированный цикл (baseline) и адаптивный.

Контроллер только *предлагает* решение («закончить зелёный, следующая фаза q»).
Тайминги (min/max зелёный, жёлтый, all-red) и безопасность обеспечивает автомат
сигналов (`signals.py`): он не спрашивает контроллер до истечения min_green, сам
обрывает зелёный на max_green и отвергает недопустимую следующую фазу (→ FAULT).

Адаптивное правило — «простое правило по наибольшему спросу с защитой от
голодания». Это эвристика, а не оптимизация: не max-pressure, не RL, не какой-либо
опубликованный алгоритм.

Спрос (считается движком по фактическому состоянию модели):

    D(g) = Σ по машинам v, стоящим в очереди к группе g (встали и ещё не проехали
           стоп-линию), (1 + w · wait_v)
    D(p) = Σ_{g ∈ p} D(g)

Единица спроса — одна машина в очереди; слагаемое w · wait_v (w =
`adaptive.wait_weight_per_sec`, по умолчанию 0.1 1/с) добавляет к машине одну
«условную машину» за каждые 1/w секунд её ожидания. Без второго слагаемого
одинокая машина на редкой полосе проигрывала бы любой очереди из двух машин
сколь угодно долго (пока не сработает защита от голодания); с ним её вес растёт
со временем. Сумма по машинам = queued_g + w · Σwait — то есть это взвешенная
сумма числа ожидающих и их суммарного (= n · среднего) ожидания.

Правила окончания зелёного активной фазы p (проверяются только после min_green,
в этом порядке):

 1. Защита от голодания: есть машина группы g ∉ p, чьё ожидание + жёлтый + all-red
    ≥ max_red_wait_sec → закончить, следующая — фаза, обслуживающая g.
 2. Gap-out: с последнего «срабатывания» прошло ≥ gap_out_sec И у какой-то другой
    фазы спрос D > 0 → закончить. Срабатывание — машина, обслуживаемая фазой p,
    проехала виртуальный детектор (detector_distance_m до стоп-линии) или
    стоп-линию. Если активной фазе нечего пропускать, срабатываний нет, и фаза
    уступает раньше max_green — «не держать зелёный впустую».
 3. Очистка очереди: у фазы p не осталось машин в очереди (все вставшие проехали
    стоп-линию), а спрос другой фазы D ≥ `adaptive.queue_clear_min_demand` (по
    умолчанию 2.0 ≈ две ждущие машины) → закончить, даже если на p ещё подъезжают
    машины со свободной скоростью. Зачем: на 2–3-полосных фазах машины с разных
    полос проезжают детектор почти непрерывно, gap-out почти не срабатывает, и без
    этого правила зелёный тянулся до max_green, пока поперечные очереди росли
    (измерено: на 5 из 8 многополосных шаблонов адаптивный режим без правила был
    не лучше фиксированного; см. VERIFICATION_STAGE2.md, раздел 6).
 4. Иначе — продлевать. Если у других фаз спроса нет, зелёный «отдыхает» на
    активной фазе (переключать некому), но не дольше max_green — это обрывает
    сам автомат.

Выбор следующей фазы: сначала голодающая (ожидание ≥ max_red_wait − (жёлтый +
all-red) − (max min_green + жёлтый + all-red), т.е. если её отложить ещё на одну
чужую фазу, она опоздает); иначе — допустимая фаза с наибольшим D(p); при равенстве
— ближайшая по циклическому порядку; если спроса нет нигде — следующая по циклу.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.simulation.models import IntersectionProfile, phase_path

if TYPE_CHECKING:  # pragma: no cover
    from app.simulation.signals import SignalMachine


@dataclass
class DemandView:
    """Срез спроса, который движок передаёт автомату на каждом тике."""

    # D(g) по формуле выше
    group_demand: dict[str, float] = field(default_factory=dict)
    # максимальное ожидание (с) среди машин в очереди к группе g
    group_max_wait: dict[str, float] = field(default_factory=dict)
    # тик последнего срабатывания детектора/стоп-линии машиной группы g
    group_last_actuation: dict[str, int] = field(default_factory=dict)
    # число машин в очереди к группе g (встали и ещё не проехали стоп-линию)
    group_queue_count: dict[str, int] = field(default_factory=dict)


@dataclass
class Decision:
    end: bool
    reason: str = ""
    next_phase: str | None = None


class BaseController:
    mode = "base"

    def __init__(self, profile: IntersectionProfile):
        self.profile = profile

    def initial_phase(self, demand: DemandView) -> str:
        return self.profile.phase_order[0]

    def decide(self, m: "SignalMachine", demand: DemandView) -> Decision:  # pragma: no cover
        raise NotImplementedError

    def choose_next(self, m: "SignalMachine", demand: DemandView) -> tuple[str, str]:
        nxt = self.profile.cycle_next(m.phase)
        return nxt, "cycle"

    def estimate_remaining_sec(self, m: "SignalMachine", demand: DemandView) -> float:
        return max(0.0, m.max_green_sec(m.phase) - m.elapsed_sec)


class FixedTimeController(BaseController):
    """Каждой фазе — заранее заданный зелёный (`fixed_green_sec`), строго по циклу.

    Спрос не учитывается вовсе: это контрольная группа для сравнения.
    """

    mode = "fixed"

    def decide(self, m: "SignalMachine", demand: DemandView) -> Decision:
        if m.elapsed_ticks >= m.ticks(self.profile.phase(m.phase).fixed_green_sec):
            return Decision(True, "fixed", self.profile.cycle_next(m.phase))
        return Decision(False)

    def estimate_remaining_sec(self, m: "SignalMachine", demand: DemandView) -> float:
        return max(0.0, self.profile.phase(m.phase).fixed_green_sec - m.elapsed_sec)


class AdaptiveController(BaseController):
    mode = "adaptive"

    # --- спрос ---

    def phase_demand(self, phase_id: str, demand: DemandView) -> float:
        return sum(demand.group_demand.get(g, 0.0) for g in self.profile.phase(phase_id).signal_groups)

    def _clearance(self) -> float:
        t = self.profile.timings
        return t.yellow_sec + t.all_red_clearance_sec

    def _starving_group(self, active: str | None, demand: DemandView, slack_sec: float) -> str | None:
        """Группа вне активной фазы с наибольшим ожиданием, если оно ≥ порога."""
        active_groups = set(self.profile.phase(active).signal_groups) if active else set()
        threshold = self.profile.timings.max_red_wait_sec - slack_sec
        worst, worst_wait = None, -1.0
        for g, w in demand.group_max_wait.items():
            if g in active_groups:
                continue
            if w >= threshold - 1e-9 and w > worst_wait:
                worst, worst_wait = g, w
        return worst

    def _phase_for_group(self, active: str | None, group: str, demand: DemandView) -> str:
        """Следующая фаза на пути к обслуживанию группы (напрямую, если переход разрешён)."""
        serving = [p.id for p in self.profile.phases if group in p.signal_groups]
        if active is None:
            return max(serving, key=lambda pid: self.phase_demand(pid, demand))
        allowed = set(self.profile.allowed_next(active))
        direct = [pid for pid in serving if pid in allowed]
        if direct:
            return max(direct, key=lambda pid: self.phase_demand(pid, demand))
        paths = [phase_path(self.profile, active, pid) for pid in serving]
        paths = [pth for pth in paths if pth]
        return min(paths, key=len)[0]

    def _others_have_demand(self, active: str, demand: DemandView) -> bool:
        return any(
            self.phase_demand(p.id, demand) > 0 for p in self.profile.phases if p.id != active
        )

    def _gap_sec(self, m: "SignalMachine", demand: DemandView) -> float:
        last = m.state_entered_tick
        for g in self.profile.phase(m.phase).signal_groups:
            last = max(last, demand.group_last_actuation.get(g, last))
        return (m.tick - last) * m.dt

    # --- интерфейс контроллера ---

    def initial_phase(self, demand: DemandView) -> str:
        starving = self._starving_group(None, demand, self._choose_slack())
        if starving:
            return self._phase_for_group(None, starving, demand)
        best = max(self.profile.phase_order, key=lambda pid: self.phase_demand(pid, demand))
        return best if self.phase_demand(best, demand) > 0 else self.profile.phase_order[0]

    def decide(self, m: "SignalMachine", demand: DemandView) -> Decision:
        starving = self._starving_group(m.phase, demand, self._clearance())
        if starving:
            return Decision(True, "starvation", self._phase_for_group(m.phase, starving, demand))
        if self._gap_sec(m, demand) >= self.profile.timings.gap_out_sec and self._others_have_demand(
            m.phase, demand
        ):
            nxt, _ = self.choose_next(m, demand)
            return Decision(True, "gap_out", nxt)
        threshold = self.profile.adaptive.queue_clear_min_demand
        if threshold is not None:
            queued = sum(demand.group_queue_count.get(g, 0) for g in self.profile.phase(m.phase).signal_groups)
            best_other = max(
                (self.phase_demand(p.id, demand) for p in self.profile.phases if p.id != m.phase), default=0.0
            )
            if queued == 0 and best_other >= threshold - 1e-9:
                nxt, _ = self.choose_next(m, demand)
                return Decision(True, "queue_clear", nxt)
        return Decision(False)

    def _choose_slack(self) -> float:
        t = self.profile.timings
        max_min_green = max(self.profile.min_green(p.id) for p in self.profile.phases)
        return self._clearance() + max_min_green + t.yellow_sec + t.all_red_clearance_sec

    def choose_next(self, m: "SignalMachine", demand: DemandView) -> tuple[str, str]:
        active = m.phase
        starving = self._starving_group(active, demand, self._choose_slack())
        if starving:
            return self._phase_for_group(active, starving, demand), "starvation"
        candidates = self.profile.allowed_next(active)
        order = self.profile.phase_order
        pos = order.index(active)

        def key(pid: str):
            dist = (order.index(pid) - pos) % len(order)
            return (-self.phase_demand(pid, demand), dist)

        best = min(candidates, key=key)
        if self.phase_demand(best, demand) > 0:
            return best, "max_demand"
        cyc = self.profile.cycle_next(active)
        return (cyc if cyc in candidates else best), "cycle_no_demand"

    def estimate_remaining_sec(self, m: "SignalMachine", demand: DemandView) -> float:
        to_max = max(0.0, m.max_green_sec(m.phase) - m.elapsed_sec)
        to_min = m.min_green_sec(m.phase) - m.elapsed_sec
        if to_min > 0:
            return to_min
        if not self._others_have_demand(m.phase, demand):
            return to_max
        to_gap = max(0.0, self.profile.timings.gap_out_sec - self._gap_sec(m, demand))
        return min(to_max, to_gap)


def make_controller(mode: str, profile: IntersectionProfile) -> BaseController:
    if mode == "fixed":
        return FixedTimeController(profile)
    if mode == "adaptive":
        return AdaptiveController(profile)
    raise ValueError(f"неизвестный режим контроллера: {mode}")
