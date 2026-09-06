from __future__ import annotations

import threading
from typing import Any

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .api import GameBoostAPI
from .config import load_config, save_config
from .latency import build_profile_probe_targets, measure_health_url, measure_tcp_targets
from .wireguard import build_config, generate_keypair, install_tunnel_service, is_admin, uninstall_tunnel_service, write_config


class WorkerSignals(QObject):
    done = Signal(object)
    error = Signal(str)


def run_bg(fn, on_done, on_error):
    sig = WorkerSignals()
    sig.done.connect(on_done)
    sig.error.connect(on_error)

    def target():
        try:
            sig.done.emit(fn())
        except Exception as exc:
            sig.error.emit(str(exc))

    threading.Thread(target=target, daemon=True).start()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GameBoost 遊戲加速器")
        self.resize(980, 680)
        self.api: GameBoostAPI | None = None
        self.games: list[dict[str, Any]] = []
        self.nodes: list[dict[str, Any]] = []
        self.measurements: dict[str, dict] = {}
        self.current_lease_id: str | None = None
        self.client_private_key: str | None = None
        self.client_public_key: str | None = None
        self.recommended_node_id: str | None = None
        self.last_direct_measurement: dict[str, Any] = {}
        self._build_ui()
        self._load_saved()

    def _build_ui(self) -> None:
        root = QWidget()
        main = QVBoxLayout(root)

        login_box = QGroupBox("帳號與 API")
        form = QFormLayout(login_box)
        self.api_url = QLineEdit("http://127.0.0.1:8080")
        self.email = QLineEdit("demo@example.com")
        self.password = QLineEdit("demo123456")
        self.password.setEchoMode(QLineEdit.Password)
        self.login_btn = QPushButton("登入")
        self.login_btn.clicked.connect(self.login)
        form.addRow("API URL", self.api_url)
        form.addRow("Email", self.email)
        form.addRow("Password", self.password)
        form.addRow(self.login_btn)
        main.addWidget(login_box)

        pick_box = QGroupBox("遊戲與節點")
        pick_layout = QVBoxLayout(pick_box)
        row = QHBoxLayout()
        self.game_combo = QComboBox()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["auto", "full", "split"])
        self.refresh_btn = QPushButton("刷新遊戲/節點")
        self.refresh_btn.clicked.connect(self.refresh_data)
        self.measure_btn = QPushButton("測節點")
        self.measure_btn.clicked.connect(self.measure_nodes)
        self.evaluate_btn = QPushButton("路由評估")
        self.evaluate_btn.clicked.connect(self.evaluate_route)
        row.addWidget(QLabel("遊戲"))
        row.addWidget(self.game_combo, 2)
        row.addWidget(QLabel("模式"))
        row.addWidget(self.mode_combo)
        row.addWidget(self.refresh_btn)
        row.addWidget(self.measure_btn)
        row.addWidget(self.evaluate_btn)
        pick_layout.addLayout(row)

        self.node_table = QTableWidget(0, 6)
        self.node_table.setHorizontalHeaderLabels(["選擇", "節點", "地區", "城市", "RTT", "Loss"])
        self.node_table.horizontalHeader().setStretchLastSection(True)
        pick_layout.addWidget(self.node_table)
        main.addWidget(pick_box)

        action_row = QHBoxLayout()
        self.connect_btn = QPushButton("一鍵連線")
        self.connect_btn.clicked.connect(self.connect_vpn)
        self.disconnect_btn = QPushButton("斷線")
        self.disconnect_btn.clicked.connect(self.disconnect_vpn)
        action_row.addWidget(self.connect_btn)
        action_row.addWidget(self.disconnect_btn)
        main.addLayout(action_row)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        main.addWidget(self.log, 1)
        self.setCentralWidget(root)

    def _load_saved(self) -> None:
        cfg = load_config()
        self.api_url.setText(cfg.get("api_url", self.api_url.text()))
        self.email.setText(cfg.get("email", self.email.text()))

    def info(self, text: str) -> None:
        self.log.appendPlainText(text)

    def show_error(self, text: str) -> None:
        self.info("錯誤：" + text)
        QMessageBox.warning(self, "GameBoost", text)

    def login(self) -> None:
        save_config({"api_url": self.api_url.text().strip(), "email": self.email.text().strip()})
        self.api = GameBoostAPI(self.api_url.text().strip())
        self.info("登入中...")
        run_bg(lambda: self.api.login(self.email.text().strip(), self.password.text()), self._login_done, self.show_error)

    def _login_done(self, data: dict) -> None:
        self.info(f"登入成功：{data['email']} / {data['plan']}")
        self.refresh_data()

    def refresh_data(self) -> None:
        if not self.api:
            self.show_error("請先登入")
            return
        self.info("刷新遊戲與節點...")
        def task():
            return self.api.games(), self.api.nodes()
        run_bg(task, self._refresh_done, self.show_error)

    def _refresh_done(self, data) -> None:
        self.games, self.nodes = data
        self.game_combo.clear()
        for game in self.games:
            self.game_combo.addItem(game.get("name", game["id"]), game["id"])
        self._render_nodes()
        self.info(f"已載入 {len(self.games)} 個遊戲 profile、{len(self.nodes)} 個節點")

    def _render_nodes(self) -> None:
        self.node_table.setRowCount(len(self.nodes))
        for row, node in enumerate(self.nodes):
            node_id = node["id"]
            selected = "✓" if node_id == self.recommended_node_id or (self.recommended_node_id is None and row == 0) else ""
            measurement = self.measurements.get(node_id, {})
            values = [selected, node.get("name", node_id), node.get("region", ""), node.get("city", ""), str(measurement.get("rtt_ms", "-")), str(measurement.get("loss_percent", "-"))]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setTextAlignment(Qt.AlignCenter)
                self.node_table.setItem(row, col, item)

    def selected_node_id(self) -> str | None:
        row = self.node_table.currentRow()
        if row < 0 and self.nodes:
            row = 0
        if row < 0:
            return None
        return self.nodes[row]["id"]

    def select_node_row(self, node_id: str) -> None:
        for row, node in enumerate(self.nodes):
            if node["id"] == node_id:
                self.node_table.selectRow(row)
                self.recommended_node_id = node_id
                return

    def measure_nodes(self) -> None:
        if not self.nodes:
            self.show_error("沒有節點可測，請先刷新")
            return
        self.info("開始測節點延遲...")
        def task():
            result = {}
            for node in self.nodes:
                result[node["id"]] = measure_health_url(node["health_url"])
            return result
        run_bg(task, self._measure_done, self.show_error)

    def _measure_done(self, result: dict) -> None:
        self.measurements = result
        self.nodes.sort(key=lambda n: (self.measurements.get(n["id"], {}).get("loss_percent", 100), self.measurements.get(n["id"], {}).get("rtt_ms") or 99999))
        self._render_nodes()
        self.info("測速完成，已依 loss / RTT 排序")

    def current_game(self) -> dict[str, Any] | None:
        game_id = self.game_combo.currentData()
        for game in self.games:
            if game.get("id") == game_id:
                return game
        return None

    def evaluate_route(self) -> None:
        if not self.api:
            self.show_error("請先登入")
            return
        if not self.nodes:
            self.show_error("沒有節點可評估，請先刷新")
            return
        game = self.current_game()
        if not game:
            self.show_error("請選遊戲")
            return
        mode = self.mode_combo.currentText()
        self.info("正在評估直連與加速路徑...")

        def task():
            measurements = dict(self.measurements)
            if not measurements:
                for node in self.nodes:
                    measurements[node["id"]] = measure_health_url(node["health_url"])
            targets = build_profile_probe_targets(game)
            direct = measure_tcp_targets(targets) if targets else {"rtt_ms": None, "loss_percent": None, "jitter_ms": None, "target_count": 0, "results": []}
            plan = self.api.route_evaluate(game["id"], mode, measurements, direct)
            return {"measurements": measurements, "direct": direct, "plan": plan}

        run_bg(task, self._evaluate_done, self.show_error)

    def _evaluate_done(self, result: dict) -> None:
        self.measurements = result["measurements"]
        self.nodes.sort(key=lambda n: (self.measurements.get(n["id"], {}).get("loss_percent", 100), self.measurements.get(n["id"], {}).get("rtt_ms") or 99999))
        self._render_nodes()

        plan = result["plan"]
        direct = result["direct"]
        node = plan["node"]
        self.last_direct_measurement = direct
        self.select_node_row(node["id"])
        node_measurement = self.measurements.get(node["id"], {})
        direct_rtt = direct.get("rtt_ms")
        direct_loss = direct.get("loss_percent")
        node_rtt = node_measurement.get("rtt_ms")
        node_loss = node_measurement.get("loss_percent")
        score = plan.get("decision", {}).get("score")
        recommendation = plan.get("recommendation", {})

        self.info(f"路由評估：{plan['game']['name']} / 模式 {plan['targets']['mode']}")
        if direct.get("target_count"):
            self.info(f"直連可測 endpoint：RTT {direct_rtt} ms / loss {direct_loss}% / targets {direct['target_count']}")
        else:
            self.info("直連 endpoint：此 profile 沒有可 TCP 測試的 domain，先以節點入口品質判斷")
        self.info(f"建議節點：{node['name']} / 入口 RTT {node_rtt} ms / loss {node_loss}% / route score {score}")
        if plan.get("candidates"):
            ranked = ", ".join(f"{item['node']['name']}={item['route_score']}" for item in plan["candidates"][:3])
            self.info(f"候選節點分數：{ranked}")
        self.info(f"建議：{recommendation.get('message', '需要更多資料')} / confidence {recommendation.get('confidence', '-')}")

    def connect_vpn(self) -> None:
        if not self.api:
            self.show_error("請先登入")
            return
        if not is_admin():
            self.show_error("請用系統管理員身分開啟 App，否則無法建立 WireGuard tunnel service。")
            return
        game_id = self.game_combo.currentData()
        if not game_id:
            self.show_error("請選遊戲")
            return
        node_id = self.selected_node_id()
        mode = self.mode_combo.currentText()
        self.info("建立 WireGuard key 並申請節點租約...")

        def task():
            self.client_private_key, self.client_public_key = generate_keypair()
            lease = self.api.start_lease(game_id, mode, self.client_public_key, node_id, self.measurements, self.last_direct_measurement)
            conf = build_config(self.client_private_key, lease)
            path = write_config(conf)
            install_tunnel_service(path)
            return lease
        run_bg(task, self._connect_done, self.show_error)

    def _connect_done(self, lease: dict) -> None:
        self.current_lease_id = lease["lease_id"]
        node = lease["node"]
        game = lease["game"]
        mode = lease["wireguard"]["targets"]["mode"]
        self.info(f"已連線：{game['name']} -> {node['name']} / 模式：{mode}")

    def disconnect_vpn(self) -> None:
        if not is_admin():
            self.show_error("請用系統管理員身分開啟 App。")
            return
        lease_id = self.current_lease_id
        self.info("正在斷線...")
        def task():
            uninstall_tunnel_service(ignore_errors=True)
            if lease_id and self.api:
                self.api.stop_lease(lease_id)
            return True
        run_bg(task, self._disconnect_done, self.show_error)

    def _disconnect_done(self, ok: bool) -> None:
        self.current_lease_id = None
        self.info("已斷線")
