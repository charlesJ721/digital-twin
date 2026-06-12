---
layer: 手段层
date: "2026-06-12"
tags:
  - VPS
  - 代理
  - 教程
  - DMIT
dg-publish: true
---

# 自建 VPS 代理：从购买到完整方案

> 创建：2026-06-12 | 目标：从 DMIT VPS 裸机开始，逐层搭建个人独立代理基础设施
> 
> 原则：每层一个可验证的里程碑，不提前做下层的活。最小可用先行，按需升级。

---

## 架构预览

```
Phase 1: 买机器 → SSH 进去 → 能跑通
Phase 2: 最小代理 → 手机/电脑能用
Phase 3: 协议升级 → 抗封锁
Phase 4: 性能调优 → 跑满带宽
Phase 5: 高可用 → 挂了自动切
Phase 6: 住宅 IP → 过流媒体/风控
```

---

## Phase 1：购买与初始化

### 1.1 购买 DMIT LAX.AN5.Pro.TINY

```
配置: 1 vCore / 2GB RAM / 20GB SSD / 1TB 流量 / 1Gbps
价格: $12.98/月 (或等年付/季付优惠)
机房: 洛杉矶 CN2 GIA 三网回程
```

买完等开机（通常 5-10 分钟）。收到邮件后拿到 IP、root 密码。

### 1.2 首次 SSH 登录

```bash
# 登录（替换为你的 IP）
ssh root@你的IP

# 改 root 密码
passwd

# 更新系统
apt update && apt upgrade -y
```

### 1.3 创建日常用户（别用 root 跑东西）

```bash
# 创建用户
useradd -m -s /bin/bash ars
passwd ars

# 给 sudo 权限
usermod -aG sudo ars

# 切到新用户
su - ars
```

### 1.4 SSH Key 认证（省得每次输密码）

```bash
# 在本地 Mac 上生成 key（如果还没有）
ssh-keygen -t ed25519 -C "dmit-la"

# 复制公钥到 VPS
ssh-copy-id ars@你的IP

# 回到 VPS，加固 SSH 配置
sudo vim /etc/ssh/sshd_config

# 改这几行：
# PermitRootLogin no
# PasswordAuthentication no
# PubkeyAuthentication yes

sudo systemctl restart sshd
```

**验证：新开一个终端窗口，`ssh ars@你的IP` 应该无密码登录。** 确认后再关旧窗口。

### 1.5 基础防火墙

```bash
sudo apt install ufw -y
sudo ufw allow 22/tcp        # SSH
sudo ufw allow 443/tcp        # 后续代理端口
sudo ufw allow 80/tcp         # 后续可能用
sudo ufw enable
sudo ufw status
```

**里程碑：能无密码 SSH 登录，防火墙已开。**

---

## Phase 2：最小代理（Shadowsocks + 简单混淆）

如果只是让自己能用，先别上复杂协议。最简单的能跑起来再说。

### 2.1 安装 Shadowsocks-rust（性能最好）

```bash
sudo apt install curl -y
curl -LO https://github.com/shadowsocks/shadowsocks-rust/releases/latest/download/shadowsocks-rust.x86_64-unknown-linux-gnu.tar.xz
tar xf shadowsocks-rust.x86_64-unknown-linux-gnu.tar.xz
sudo mv ssserver /usr/local/bin/
rm shadowsocks-rust*
```

### 2.2 配置

```bash
sudo mkdir -p /etc/shadowsocks
sudo vim /etc/shadowsocks/config.json
```

```json
{
  "server": "0.0.0.0",
  "server_port": 443,
  "password": "生成一个随机密码",
  "method": "chacha20-ietf-poly1305",
  "fast_open": true
}
```

生成随机密码：`openssl rand -base64 32`

### 2.3 注册为系统服务

```bash
sudo vim /etc/systemd/system/shadowsocks.service
```

```
[Unit]
Description=Shadowsocks Server
After=network.target

[Service]
Type=simple
User=nobody
ExecStart=/usr/local/bin/ssserver -c /etc/shadowsocks/config.json
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable shadowsocks --now
sudo systemctl status shadowsocks
```

### 2.4 客户端连接

- iOS：Shadowrocket / Stash
- macOS：Clash Verge（你已在用）
- 协议选 Shadowsocks，填 IP、端口 443、密码、加密方法

**里程碑：手机切 4G，连上后能打开 google.com。**

---

## Phase 3：协议升级（VLESS + XTLS + REALITY）

Phase 2 的 Shadowsocks 容易被主动探测识别。升级到 VLESS + XTLS + REALITY 后流量看起来像正常的 HTTPS 访问某个网站。

### 3.1 安装 Xray-core

```bash
# 官方脚本
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
```

### 3.2 生成 REALITY 密钥

```bash
xray x25519
# 记下 Private key 和 Public key
```

### 3.3 配置

```bash
sudo vim /usr/local/etc/xray/config.json
```

```json
{
  "log": {"loglevel": "warning"},
  "inbounds": [{
    "port": 443,
    "protocol": "vless",
    "settings": {
      "clients": [{
        "id": "生成一个 UUID",
        "flow": "xtls-rprx-vision"
      }],
      "decryption": "none"
    },
    "streamSettings": {
      "network": "tcp",
      "security": "reality",
      "realitySettings": {
        "dest": "www.bing.com:443",
        "serverNames": ["www.bing.com"],
        "privateKey": "刚才生成的 Private key",
        "shortIds": ["6ba85179e30d4fc2"]
      }
    }
  }],
  "outbounds": [{
    "protocol": "freedom",
    "tag": "direct"
  }]
}
```

生成 UUID：`uuidgen`

`dest` 选一个 CDN 加速的大站（bing.com、microsoft.com、cloudflare.com），域名要和自己选的服务商挨不着边。

**别忘了先停掉 Phase 2 的 Shadowsocks（占着 443 端口）：**
```bash
sudo systemctl stop shadowsocks
sudo systemctl disable shadowsocks
```

启动 Xray：
```bash
sudo systemctl restart xray
sudo systemctl status xray
```

### 3.4 客户端配置

以 Clash Verge 为例，在订阅配置或本地节点中添加：
- 协议：VLESS
- 地址：你的 IP
- 端口：443
- UUID：上面生成的
- Flow：xtls-rprx-vision
- 加密：none
- 传输：tcp
- REALITY：开启，Public key 填上面生成的，Short ID 填配置里的，Server name 填 `www.bing.com`

**里程碑：连上后流量在 ISP 侧看起来就是你正在访问 bing.com。**

---

## Phase 4：性能调优

### 4.1 开启 BBR

```bash
echo "net.core.default_qdisc=fq" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_congestion_control=bbr" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# 验证
sysctl net.ipv4.tcp_congestion_control
# 应输出: net.ipv4.tcp_congestion_control = bbr
```

### 4.2 TCP 参数优化

在 `/etc/sysctl.conf` 追加：

```
net.ipv4.tcp_slow_start_after_idle=0
net.ipv4.tcp_notsent_lowat=16384
net.ipv4.tcp_mtu_probing=1
```

应用：`sudo sysctl -p`

### 4.3 网络参数（高并发/长期连接）

```
net.core.rmem_max=67108864
net.core.wmem_max=67108864
net.ipv4.tcp_rmem=4096 87380 33554432
net.ipv4.tcp_wmem=4096 65536 33554432
```

**里程碑：晚高峰测速能达到本地带宽的 70% 以上。**

---

## Phase 5：高可用

### 5.1 自动健康检查 + 重启

```bash
sudo vim /usr/local/bin/health-check.sh
```

```bash
#!/bin/bash
# 每 5 分钟检查 Xray 是否活着，挂了就重启
if ! pgrep -x xray > /dev/null; then
  systemctl restart xray
  echo "$(date): Xray restarted" >> /var/log/xray-health.log
fi
```

```bash
sudo chmod +x /usr/local/bin/health-check.sh

# 加到 cron
(crontab -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/health-check.sh") | crontab -
```

### 5.2 自动换 IP（DMIT 支持每 15 天免费换）

在 DMIT 控制面板里可以申请更换 IP。或者当 IP 被墙时手动操作。

### 5.3 再加一个备用节点（可选扩展）

如果预算允许，可以考虑：
- 同账号再开一个 DMIT 东京或香港节点（但价格高）
- 或买一个便宜的年付 VPS 做冷备（比如 RackNerd $10/年）

在 Clash 本地配 `fallback` 代理组，主节点挂了自动切备用。

**里程碑：Xray 进程挂了 5 分钟内自动恢复。如果整机挂了（罕见），手动切到备用节点。**

---

## Phase 6：住宅 IP 层

DMIT 给的是机房 IP——虽然原生美国，但不是住宅 IP。某些场景（流媒体解锁、严格风控网站）需要住宅 IP。

### 方案：机房 VPS 前置 + 住宅代理后置

```
你 → DMIT VPS (CN2 GIA) → 住宅代理 → 目标网站
```

DMIT VPS 负责高速跨境传输，住宅代理只负责最后一跳的 IP 伪装。流量分配：
- 普通网站：DMIT 直连
- 需要住宅 IP 的网站：DMIT → 住宅代理 → 出去

实现方式取决于你选的住宅代理服务。常见选择：

**静态住宅 IP 服务（每月固定 IP）：**
- Bright Data（最成熟，$8.25/月起 + 流量费）
- IPRoyal（$2.5/月起）
- Proxy-Cheap（$2.99/月起）

**在 VPS 上用 HAProxy 做分流：**

```bash
sudo apt install haproxy -y
sudo vim /etc/haproxy/haproxy.cfg
```

核心逻辑：DMIT 本地 Xray 监听 443，对于需要住宅 IP 的流量，通过 HAProxy 转发到住宅代理；其余直连。

**如果不想自己维护分流规则——更简单的做法：**
本地 Clash 里直接配两条策略组：
- `节点-DMIT`：直连 DMIT VPS
- `节点-住宅`：DMIT → 住宅代理

在 Clash 规则里指定哪些网站走住宅线路。

**里程碑：Netflix/Hulu/银行网站不再提示代理/VPN。**

---

## 运维备忘

### 常用命令

```bash
# 看流量
sudo vnstat -m    # 需 apt install vnstat

# 看当前连接
ss -tnp | grep xray

# 重启代理
sudo systemctl restart xray

# 看日志
sudo journalctl -u xray -f

# 更新系统
sudo apt update && sudo apt upgrade -y && sudo reboot
```

### DMIT 控制面板常用操作
- 换 IP：Dashboard → 选中实例 → Change IP
- 重装系统：Dashboard → Reinstall
- 流量统计：Dashboard 首页可见

### 成本核算

| 层级 | 方案 | 月费 |
|---|---|---|
| VPS | DMIT LAX.AN5.Pro.TINY | $12.98 |
| 住宅 IP | IPRoyal 静态住宅 | $2.50 |
| **合计** | | **~$15.5/月** |

对比 rancho VPN 订阅通常 $6-10/月——贵一倍，但换来的是：
- 独享带宽，高峰期不拥堵
- 真正的 CN2 GIA 线路（不是公网 163）
- IP 不会被共享用户搞黑
- 完全控制协议和配置

---

## 升级路线总结

```
Phase 1 ──→ SSH 能进去 ✓
Phase 2 ──→ Shadowsocks 能用 ✓  （第一天就能到这）
Phase 3 ──→ VLESS+REALITY 抗封锁 ✓
Phase 4 ──→ BBR + TCP 优化 ✓
Phase 5 ──→ 自动重启 + 备用节点 ✓
Phase 6 ──→ 住宅 IP 解除风控 ✓
```

每做完一层，稳定用几天再往上走。不要一步到位。
