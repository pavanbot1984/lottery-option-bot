# otm_option_monitor.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, List, Dict
from datetime import datetime

Side = Literal["CALL","PUT"]

@dataclass
class Action:
    kind: str              # ENTRY50 | ADD50 | EXIT_SL | TP_HIT | TRAIL_UPDATE | TRAIL_EXIT
    side: Side
    strike: float
    size_btc: float
    mark: float
    note: str
    date: str
    time: str
    trade_id: str = ""
    direction: str = ""    # BULL for CALL, BEAR for PUT
    stage: int = None

class SingleOptionMonitor:
    """
    Per-option monitor using that option's own chart.
    BOTH CALL and PUT enter on bullish 5m flips (per your rule).
    All state-changing decisions can be forced to run ONLY on closed bars
    by passing bar_closed=True to update().
    """
    def __init__(
        self,
        side: Side,
        strike: float,
        half_size_btc: float = 0.005,
        rr_mult: float = 1.0,
        trail_drop_pct: float = 0.25,
        rsi_bull_min: float = 55.0,
        only_on_bar_close: bool = True,
    ):
        self.side = side
        self.strike = float(strike)
        self.half = half_size_btc
        self.rr_mult = rr_mult
        self.trail = trail_drop_pct
        self.rsi_bull_min = rsi_bull_min
        self.only_on_bar_close = only_on_bar_close
        # state
        self.stage = 0
        self.size = 0.0
        self.wap = 0.0
        self.tp_hit = False
        self.peak = 0.0

    def _stamp(self) -> Dict[str, str]:
        now = datetime.now()
        return {"date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M:%S")}

    def update(
        self,
        *,
        st5_dir: int,
        st15_dir: int,
        rsi_value: float,
        macd_hist_value: float,
        mark: float,
        bar_closed: bool,
    ) -> List[Action]:
        """
        bar_closed = True  => act (like TradingView close)
        bar_closed = False => ignore (no new entries/exits, just internal peak track after TP)
        """
        acts: List[Action] = []
        ts = self._stamp()

        # During live bar, optionally do nothing (prevents premature flips)
        if self.only_on_bar_close and not bar_closed:
            # still track peak if we already hit TP (no exits/entries)
            if self.stage > 0 and self.tp_hit:
                if mark > self.peak:
                    self.peak = float(mark)
                    acts.append(Action("TRAIL_UPDATE", self.side, self.strike, 0.0, mark, f"peak {self.peak:.2f}", **ts, direction=("BULL" if self.side=="CALL" else "BEAR")))
            return acts

        # BOTH CALL & PUT favor bullish flips on their own charts
        favor_5m = (st5_dir > 0)
        favor_15m = (st15_dir > 0)
        against_5m = (st5_dir < 0)

        # Stage 1
        if self.stage == 0 and favor_5m:
            self.stage = 1
            self.size = self.half
            self.wap = float(mark)
            self.peak = float(mark)
            acts.append(Action("ENTRY50", self.side, self.strike, self.half, mark, "5m ST flip (closed bar)", **ts, direction=("BULL" if self.side=="CALL" else "BEAR"), stage=1))
            return acts

        # Stage 2 (15m confirm + MACD/RSI bullish)
        if self.stage == 1 and favor_15m:
            if (rsi_value >= self.rsi_bull_min) and (macd_hist_value > 0):
                new_wap = (self.wap*self.size + mark*self.half) / (self.size + self.half)
                self.wap = new_wap
                self.size += self.half
                self.stage = 2
                self.peak = max(self.peak, float(mark))
                acts.append(Action("ADD50", self.side, self.strike, self.half, mark, "15m confirm + MACD/RSI (closed bar)", **ts, direction=("BULL" if self.side=="CALL" else "BEAR"), stage=2))

        # SL on 5m flip against
        if self.stage > 0 and against_5m:
            acts.append(Action("EXIT_SL", self.side, self.strike, self.size, mark, "5m ST flip against (closed bar)", **ts, direction=("BULL" if self.side=="CALL" else "BEAR")))
            self._reset()
            return acts

        # Profit mgmt (on bar close)
        if self.stage > 0:
            if mark > self.peak:
                self.peak = float(mark)
            tp_level = self.wap * (1.0 + self.rr_mult)  # 2x WAP when rr_mult=1.0
            if not self.tp_hit and mark >= tp_level:
                self.tp_hit = True
                acts.append(Action("TP_HIT", self.side, self.strike, 0.0, mark, f"target {tp_level:.2f} reached", **ts, direction=("BULL" if self.side=="CALL" else "BEAR")))
            if self.tp_hit:
                if mark <= self.peak * (1.0 - self.trail):
                    acts.append(Action("TRAIL_EXIT", self.side, self.strike, self.size, mark, f"drop {self.trail*100:.0f}% from peak", **ts, direction=("BULL" if self.side=="CALL" else "BEAR")))
                    self._reset()
                else:
                    acts.append(Action("TRAIL_UPDATE", self.side, self.strike, 0.0, mark, f"peak {self.peak:.2f}", **ts, direction=("BULL" if self.side=="CALL" else "BEAR")))
        return acts

    def _reset(self):
        self.stage = 0
        self.size = 0.0
        self.wap = 0.0
        self.tp_hit = False
        self.peak = 0.0
