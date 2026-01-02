import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from agents.application.trade import Trader

import time

from scheduler import Scheduler
from scheduler.trigger import Monday


class Scheduler:
    def __init__(self) -> None:
        self.trader = Trader()
        self.schedule = Scheduler()

    def start(self) -> None:
        while True:
            self.schedule.exec_jobs()
            time.sleep(1)


class TradingAgent(Scheduler):
    def __init__(self) -> None:
        super()
        self.trader = Trader()
        self.weekly(Monday(), self.trader.one_best_trade)
