# hcmus-discord-notifier

Discord Bot gửi thông báo khi có bài đăng mới từ các RSS feed của **Trường ĐH Khoa học Tự nhiên (HCMUS)**, **Khoa CNTT (FIT)** và **Phòng Khảo thí & ĐBCL**.

---

## Tính năng

- 🔔 Tự động kiểm tra bài đăng mới mỗi **10 phút**.
- 🛡️ Quản lý server và kênh thông báo qua slash commands.


## Yêu cầu hệ thống

Thay đổi theo từng phiên bản, chi tiết xem tại [Release](https://github.com/itsccao/hcmus-discord-notifier/releases).

## Cài đặt

### 1. Clone repository

```bash
git clone https://github.com/itsccao/hcmus-discord-notifier.git
cd hcmus-discord-notifier
```

### 2. Thiết lập Virtual Environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Cài đặt các thư viện cần thiết

```bash
pip install -r requirements.txt
```

### 4. Thêm các thông tin cần thiết khác

Sao chép file mẫu và điền thông tin:

```bash
cp .env.example .env
```

Mở file `.env` và điền đầy đủ các thông tin:

| Variable | Mô tả |
|------|-------|
| `BOT_TOKEN` | Token của bot lấy từ [Discord Developer Portal](https://discord.com/developers/applications) |
| `BOT_NAME` | Tên hiển thị của bot trong server (mặc định: `Delta`) |
| `OWNER_ID` | Discord User ID của chủ bot — dùng để xác thực lệnh admin |

> **Lấy User ID**: Bật Developer Mode trong Discord → chuột phải vào tên mình → *Copy User ID*.

### 5. Cấu hình Discord Bot

Vào [Discord Developer Portal](https://discord.com/developers/applications), chọn bot của bạn:

- **Bot → Privileged Gateway Intents**: bật `Server Members Intent` và `Message Content Intent`
- **OAuth2 → URL Generator**: chọn scope `bot` + `applications.commands`, permission tối thiểu: `Send Messages`, `Embed Links`, `Read Message History`

### 6. Chạy bot

```bash
python bot.py
```

## Danh sách lệnh

### 📢 Thông báo

| Lệnh | Mô tả |
|------|-------|
| `!check-rss` | Xem bài đăng mới nhất từ tất cả RSS feed đang theo dõi |

### 🛠️ Hệ thống

| Lệnh | Mô tả |
|------|-------|
| `!help` | Danh sách các câu lệnh |
| `!about` | Thông tin về bot |
| `!ping` | Kiểm tra độ trễ |
| `!feedback <nội dung>` | Gửi feedback cho tác giả |

### 🔒 Admins Only *(chỉ dành cho bot owner)*

| Lệnh | Mô tả |
|------|-------|
| `!guild-list` | Danh sách server bot đang hoạt động |
| `!guild-leave <guild_id>` | Buộc bot rời khỏi một server |
| `!server-allow [guild_id]` | Thêm server vào danh sách cho phép |
| `!server-deny [guild_id]` | Xóa server khỏi danh sách cho phép |
| `!server-list` | Xem danh sách server được phép |
| `!channel-add <group> [channel]` | Thêm kênh vào nhóm thông báo |
| `!channel-remove <group> [channel]` | Xóa kênh khỏi nhóm thông báo |
| `!channel-list` | Xem tất cả kênh thông báo đã đăng ký |

> Tất cả lệnh đều hỗ trợ cả prefix (`!`) lẫn slash command (`/`).

## Thêm kênh thông báo

Sau khi bot đã vào server, dùng lệnh (với tư cách bot owner):

```
/channel-add feeds #tên-kênh
```

Bot sẽ gửi thông báo vào kênh đó mỗi khi có bài đăng mới.

---

> [!NOTE]
> This project is licensed under the [GNU General Public License v3.0](./LICENSE).