# persistent-ssh-agent

<div align="center">

[![Python Version](https://img.shields.io/pypi/pyversions/persistent_ssh_agent)](https://img.shields.io/pypi/pyversions/persistent_ssh_agent)
[![Nox](https://img.shields.io/badge/%F0%9F%A6%8A-Nox-D85E00.svg)](https://github.com/wntrblm/nox)
[![PyPI Version](https://img.shields.io/pypi/v/persistent_ssh_agent?color=green)](https://pypi.org/project/persistent_ssh_agent/)
[![Downloads](https://static.pepy.tech/badge/persistent_ssh_agent)](https://pepy.tech/project/persistent_ssh_agent)
[![Downloads](https://static.pepy.tech/badge/persistent_ssh_agent/month)](https://pepy.tech/project/persistent_ssh_agent)
[![Downloads](https://static.pepy.tech/badge/persistent_ssh_agent/week)](https://pepy.tech/project/persistent_ssh_agent)
[![License](https://img.shields.io/pypi/l/persistent_ssh_agent)](https://pypi.org/project/persistent_ssh_agent/)
[![PyPI Format](https://img.shields.io/pypi/format/persistent_ssh_agent)](https://pypi.org/project/persistent_ssh_agent/)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/loonghao/persistent_ssh_agent/graphs/commit-activity)
![Codecov](https://img.shields.io/codecov/c/github/loonghao/persistent_ssh_agent)
</div>

🔐 一个用于跨会话持久化 SSH agent 管理的现代 Python 库。

[特性亮点](#特性亮点) •
[安装](#安装) •
[使用指南](#使用指南) •
[示例](#示例) •
[贡献](#贡献)

## 🎯 特性亮点

- 🔄 跨会话的持久化 SSH agent 管理
- 🔑 自动 SSH 密钥加载和缓存
- 🪟 针对 Windows 优化的实现
- 🔗 无缝 Git 集成
- 🌐 跨平台兼容性 (Windows, Linux, macOS)
- 📦 除标准 SSH 工具外无外部依赖
- 🔒 安全的密钥管理和会话控制
- ⚡ 异步操作支持
- 🧪 完整的单元测试覆盖
- 📝 类型提示支持

## 🚀 安装

```bash
pip install persistent-ssh-agent
```

## 📋 系统要求

- Python 3.8+
- OpenSSH (ssh-agent, ssh-add) 已安装且在 PATH 中可用
- Git (可选，用于 Git 操作)

## 📖 使用指南

### 基础用法

```python
from persistent_ssh_agent import PersistentSSHAgent

# 创建实例，可自定义过期时间（默认24小时）
ssh_agent = PersistentSSHAgent(expiration_time=86400)

# 为特定主机设置 SSH
if ssh_agent.setup_ssh('github.com'):
    print("✅ SSH 认证就绪！")
```

### 高级配置

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

# 创建自定义 SSH 配置
config = SSHConfig()
config.add_host_config('github.com', {
    'IdentityFile': '~/.ssh/github_key',
    'User': 'git',
    'Port': '22'
})

# 使用自定义配置初始化
ssh_agent = PersistentSSHAgent(config=config)

# 设置 SSH 认证
if ssh_agent.setup_ssh('github.com'):
    # 获取该主机的 Git SSH 命令
    ssh_command = ssh_agent.get_git_ssh_command('github.com')
    if ssh_command:
        print("✅ Git SSH 命令已就绪！")
```

### 异步操作支持

```python
import asyncio
from persistent_ssh_agent import PersistentSSHAgent

async def setup_multiple_hosts(hosts: list[str]) -> dict[str, bool]:
    """并发设置多个主机的 SSH。"""
    ssh_agent = PersistentSSHAgent()
    results = {}

    async def setup_host(host: str):
        results[host] = await ssh_agent.async_setup_ssh(host)

    await asyncio.gather(*[setup_host(host) for host in hosts])
    return results

# 使用示例
async def main():
    hosts = ['github.com', 'gitlab.com', 'bitbucket.org']
    results = await setup_multiple_hosts(hosts)
    for host, success in results.items():
        print(f"{host}: {'✅' if success else '❌'}")

asyncio.run(main())
```

### 安全最佳实践

1. **密钥管理**:
   - 将 SSH 密钥存储在标准位置 (`~/.ssh/`)
   - 使用 Ed25519 密钥以获得更好的安全性
   - 确保私钥权限正确 (600)

2. **错误处理**:
   ```python
   try:
       ssh_agent = PersistentSSHAgent()
       success = ssh_agent.setup_ssh('github.com')
       if not success:
           print("⚠️ SSH 设置失败")
   except Exception as e:
       print(f"❌ 错误: {e}")
   ```

3. **会话管理**:
   - 会话信息在重启后持久化
   - 自动清理过期会话
   - 可配置的过期时间
   - 支持多会话并发管理

4. **安全特性**:
   - 到期后自动卸载密钥
   - 安全的临时文件处理
   - 平台特定的安全措施
   - 密钥使用追踪

## 🔧 常见使用场景

### CI/CD 流水线集成

```python
import os
from persistent_ssh_agent import PersistentSSHAgent

def setup_ci_ssh():
    """为 CI 环境设置 SSH。"""
    ssh_agent = PersistentSSHAgent()

    # 从环境变量获取 SSH 密钥
    key_path = os.environ.get('SSH_PRIVATE_KEY_PATH')
    if not key_path:
        raise ValueError("未提供 SSH 密钥路径")

    if ssh_agent.start_ssh_agent(key_path):
        print("✅ SSH agent 启动成功")
        return True

    raise RuntimeError("SSH agent 启动失败")
```

### Git 操作集成

```python
from git import Repo
from persistent_ssh_agent import PersistentSSHAgent
import os

def clone_repo(repo_url: str, local_path: str, branch: str = None) -> Repo:
    """使用持久化 SSH 认证克隆仓库。"""
    ssh_agent = PersistentSSHAgent()

    # 从 URL 提取主机名并设置 SSH
    hostname = ssh_agent.extract_hostname(repo_url)
    if not hostname or not ssh_agent.setup_ssh(hostname):
        raise RuntimeError("SSH 认证设置失败")

    # 获取 SSH 命令并配置环境
    ssh_command = ssh_agent.get_git_ssh_command(hostname)
    if not ssh_command:
        raise RuntimeError("获取 SSH 命令失败")

    # 使用 GitPython 克隆
    env = os.environ.copy()
    env['GIT_SSH_COMMAND'] = ssh_command

    return Repo.clone_from(
        repo_url,
        local_path,
        branch=branch,
        env=env
    )

# 使用示例
try:
    repo = clone_repo(
        'git@github.com:username/repo.git',
        '/path/to/local/repo',
        branch='main'
    )
    print("✅ 仓库克隆成功")
except Exception as e:
    print(f"❌ 错误: {e}")
```

## 🌟 高级功能

### 自定义配置

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

# 创建配置实例
config = SSHConfig()

# 添加全局配置
config.add_global_config({
    'AddKeysToAgent': 'yes',
    'UseKeychain': 'yes'
})

# 添加主机特定配置
config.add_host_config('*.github.com', {
    'User': 'git',
    'IdentityFile': '~/.ssh/github_ed25519',
    'PreferredAuthentications': 'publickey'
})

# 使用配置初始化 agent
agent = PersistentSSHAgent(config=config)
```

### 密钥管理

```python
from persistent_ssh_agent import PersistentSSHAgent

agent = PersistentSSHAgent()

# 添加密钥
agent.add_key('~/.ssh/id_ed25519')

# 列出已加载的密钥
keys = agent.list_keys()
for key in keys:
    print(f"已加载密钥: {key}")

# 移除特定密钥
agent.remove_key('~/.ssh/id_ed25519')

# 清理所有密钥
agent.clear_keys()
```

## 🤝 贡献

欢迎贡献！请随时提交 Pull Request。

1. Fork 仓库
2. 创建您的功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m '添加了一个惊人的功能'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开一个 Pull Request

## 📄 许可

本项目使用 MIT 许可证 - 请参阅 [LICENSE](LICENSE) 文件以获取详细信息。
