# BIÊN BẢN NGHIỆM THU PRE-FLIGHT SANITY CHECK (STAGE 40.1)
**Dự án:** REGIME-ROUTER-02 — VN30F1M Futures  
**Môi trường thử nghiệm:** Linux Staging VM (Oracle Linux 9 / cgroup v2 / 512 MiB RAM)  
**Thời gian thực thi:** [YYYY-MM-DD HH:MM:SS]  
**Người thực hiện:** Technical Team | **Người phê duyệt:** Tech Lead  
**Nguyên tắc an toàn:** Zero Touch 100% đối với Production VPS (`instance-20261114-1044`, PID 139407).

---

## 1. KẾT QUẢ THỰC THI 4 TIÊU CHÍ

| STT | Hạng mục kiểm tra | Giá trị kỳ vọng | Giá trị đo được thực tế | Kết luận |
|:---:|:---|:---|:---|:---:|
| **1** | **Permission Boundary**<br>*(Thực thi qua process trong sandbox)* | - Đọc mock `.env`: `Permission Denied`<br>- Ghi mock `bot1.db`: `Permission Denied` | Đọc `.env`: `[KẾT QUẢ]`<br>Ghi DB: `[KẾT QUẢ]` | **[PASS / FAIL]** |
| **2** | **Cgroup Enforcement**<br>*(Đọc động: `systemctl show ... -p ControlGroup`)* | - `memory.high`: `62914560`<br>- `memory.max`: `78643200`<br>- `memory.swap.max`: `0`<br>- `cpu.max`: `40000 100000`<br>- `pids.max`: `30` | - `memory.high`: `[RAW]`<br>- `memory.max`: `[RAW]`<br>- `memory.swap.max`: `[RAW]`<br>- `cpu.max`: `[RAW]`<br>- `pids.max`: `[RAW]` | **[PASS / FAIL]** |
| **3** | **SQLite WAL Sanity**<br>*(500 commits vào `bot2_trades.db`)* | - `journal_mode`: `wal`<br>- `wal_checkpoint`: `0 0 0`<br>- Commits: 500/500 thành công | - `journal_mode`: `[RAW]`<br>- `wal_checkpoint`: `[RAW]`<br>- Thành công: `[X]/500` | **[PASS / FAIL]** |
| **4** | **Controlled Co-existence**<br>*(10 phút tải song song)* | - Host Used RAM: $< 350\text{ MiB}$<br>- Host & Bot2 Swap: $= 0$<br>- Bot2 `memory.current`: $< 75\text{ MiB}$<br>- Jitter $\Delta \text{P99}$: $\le 50\text{ ms}$<br>- Missed Heartbeat ($> 3\text{s}$): $0$ | - Host Used: `[X] MiB`<br>- Swap Host / Bot2: `[X] / [Y]`<br>- Bot2 peak RAM: `[X] MiB`<br>- Base P99: `[X] ms` → Coex P99: `[Y] ms`<br>  $\rightarrow \Delta \text{P99}$: `[Z] ms`<br>- Missed: `[0]` | **[PASS / FAIL]** |

---

## 2. KẾT LUẬN & ĐỀ XUẤT

- **Đánh giá tổng thể:** Toàn bộ 4/4 tiêu chí [ĐẠT / CHƯA ĐẠT] yêu cầu an toàn vận hành tối thiểu.
- **Ranh giới an toàn:** Bot 2 bị khống chế cứng trong hạn mức 75 MiB RAM, hoàn toàn không có khả năng đọc/ghi dữ liệu của Bot 1, hoạt động SQLite trơn tru và không gây suy giảm nhịp heartbeat của Bot 1 vượt quá ngưỡng dung sai cho phép.
- **Đề xuất bước tiếp theo:** [ ] Đủ điều kiện chuẩn bị quy trình Go-Live / [ ] Yêu cầu khắc phục lỗi.

**Chữ ký Kỹ sư Thực hiện:** ____________________    **Phê duyệt Tech Lead:** ____________________
