# NowCoding - 快兔算力代码创作与展示平台

一个轻量级的在线代码创作与展示平台：内置 AI 对话助手，支持代码编辑、语法高亮、实时预览、多设备模拟和一键分享。

## ✨ 功能特性

- **代码编辑器**：支持多语言语法高亮，内置 HTML/CSS/JS 编辑
- **实时预览**：编辑代码后自动渲染预览结果
- **设备模拟**：桌面 / 平板 / 手机多端预览
- **一键分享**：生成分享链接，快速展示你的代码片段
- **AI 对话助手**：内置大模型聊天，自然语言描述即可生成代码
- **作品榜单**：浏览和发现社区创作的项目
- **简洁界面**：现代化 UI 设计，响应式布局，支持移动端
- **零依赖部署**：基于 Python 标准库，无需安装任何第三方依赖

## 🚀 快速部署

### 方式一：直接运行

```bash
python3 server.py
```

服务器默认监听 `0.0.0.0:3000`，浏览器访问 `http://你的IP:3000` 即可。

### 方式二：一键部署脚本（推荐）

```bash
sudo ./deploy.sh
```

自动完成 nginx 配置软链、reload 和启动后端，一条命令搞定。

## 📁 项目结构

```
showcode/
├── index.html               # 首页 - 快兔算力导航页
├── ui.html            # 主应用 - 代码编辑器与展示界面
├── quota.html               # 我的算力额度（占位页）
├── guide.html               # 算力接入指南（占位页）
├── server.py                # Python 后端（标准库，处理 /api/save）
├── projects/                # 保存的作品落盘目录（自动创建）
├── nginx.showcode.conf      # nginx 站点配置（新服务器一键软链）
├── deploy.sh                # 全功能部署/运维脚本（见下表）
├── README.md                # 项目说明（中文）
├── README.en.md             # 项目说明（英文）
└── README.zh.md             # 项目说明（中文备份）
```

## 🔁 迁移到新服务器（标准流程）

业务代码与 nginx 完全解耦：nginx 只做反向代理和静态服务，所有业务逻辑写在 `server.py` 里。
新机器只要装 nginx + Python，把本文件夹拷过去就能跑：

```bash
# 1) 目标服务器：装标准 nginx 和 Python
sudo apt update && sudo apt install -y nginx python3

# 2) 把整个 showcode/ 目录拷到目标服务器（路径随意，例如 /opt/showcode）
sudo mkdir -p /opt && sudo cp -r showcode /opt/

# 3) 进目录跑一键部署脚本
cd /opt/showcode && sudo ./deploy.sh
```

`deploy.sh` 子命令（systemd 单元、启停脚本都合并进来）：

| 命令 | 用途 |
|------|------|
| `sudo ./deploy.sh` | 完整部署：软链 nginx 配置 + reload + 启动后端 |
| `sudo ./deploy.sh start` / `stop` / `restart` / `status` | 后端运维 |
| `sudo ./deploy.sh service` | 安装为 systemd 开机自启服务（不需单独 .service 文件）|

### 调端口/目录

只需改 `nginx.showcode.conf` 两处：

- `root /showcode;` → 改成实际目录
- `proxy_pass http://127.0.0.1:8104/v1/;` → 你的 LLM 上游（不用 AI 就整段删掉）

后端端口默认 3000，要改就改 `server.py` 里的 `PORT =`，同步改 `nginx.showcode.conf` 里 `proxy_pass` 的端口。

## 🔧 技术栈

- **前端**: HTML + CSS + JavaScript（原生，无框架依赖）
- **后端**: Python 标准库 http.server
- **部署**: systemd（支持开机自启）

## 📝 配置说明

### 修改端口

编辑 `server.py`，修改 `PORT = 3000` 为你想要的端口号：

```python
PORT = 3000   # 改为你需要的端口
```

### Nginx 反向代理（可选）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📄 许可证

MIT License
