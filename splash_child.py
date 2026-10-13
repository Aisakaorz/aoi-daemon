#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动画面子进程入口
独立进程显示启动画面：动画运行在子进程自己的事件循环中，
不被主进程的重型导入/窗口构建/模型加载阻塞，保证从显示到关闭全程流畅滚动

通信协议：主进程往本进程 stdin 写入 "close" 关闭启动画面；
管道断开（主进程退出）时自行退出，避免孤儿进程
"""
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QApplication


class _StdinWatcher(QObject):
    """后台线程监听 stdin，收到关闭指令或管道断开时发信号（Qt 队列连接回 GUI 线程）"""

    close_requested = Signal()

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            for line in sys.stdin:
                if line.strip().lower() == "close":
                    self.close_requested.emit()
                    return
        except Exception:
            pass
        # 管道断开（主进程已退出）：自行退出
        self.close_requested.emit()


def run_splash_child() -> int:
    app = QApplication(["aoi-splash"])
    from ui.splash_screen import SplashScreen

    splash = SplashScreen()
    splash.show()

    watcher = _StdinWatcher()
    watcher.close_requested.connect(splash.request_close)
    # 兜底：子进程仅有此一个窗口，收到关闭指令后在淡出余量内主动退出事件循环，
    # 避免个别平台 close() 不触发 lastWindowClosed 导致子进程残留
    watcher.close_requested.connect(
        lambda: QTimer.singleShot(SplashScreen._MIN_VISIBLE_MS + 600, app.quit)
    )
    watcher.start()

    return app.exec()


if __name__ == "__main__":
    sys.exit(run_splash_child())
