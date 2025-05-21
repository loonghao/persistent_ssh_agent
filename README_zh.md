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
config = SSHConfig(
    identity_file='~/.ssh/github_key',  # 可选的指定身份文件
    identity_passphrase='your-passphrase',  # 可选的密码短语
    ssh_options={  # 可选的 SSH 选项
        'StrictHostKeyChecking': 'yes',
        'PasswordAuthentication': 'no',
        'PubkeyAuthentication': 'yes'
    }
)

# 使用自定义配置和 agent 复用设置初始化
ssh_agent = PersistentSSHAgent(
    config=config,
    expiration_time=86400,  # 可选：设置 agent 过期时间（默认24小时）
    reuse_agent=True  # 可选：控制 agent 复用行为（默认为 True）
)

# 设置 SSH 认证
if ssh_agent.setup_ssh('github.com'):
    # 获取该主机的 Git SSH 命令
    ssh_command = ssh_agent.get_git_ssh_command('github.com')
    if ssh_command:
        print("✅ Git SSH 命令已就绪！")
```

### Agent 复用行为

`reuse_agent` 参数控制 SSH agent 如何处理现有会话：

- 当 `reuse_agent=True`（默认值）时：
  - 尝试复用现有的 SSH agent（如果可用）
  - 减少 agent 启动和密钥添加的次数
  - 通过避免不必要的 agent 操作来提高性能

- 当 `reuse_agent=False` 时：
  - 总是启动新的 SSH agent 会话
  - 当您需要全新的 agent 状态时很有用
  - 在某些对安全性要求较高的环境中可能更受欢迎

禁用 agent 复用的示例：

```python
# 总是启动新的 agent 会话
ssh_agent = PersistentSSHAgent(reuse_agent=False)
```

### CI/CD 集成

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

def setup_ci_ssh():
    """为 CI 环境设置 SSH。"""
    # 创建带有密钥内容的配置
    config = SSHConfig(
        identity_content=os.environ.get('SSH_PRIVATE_KEY'),
        ssh_options={'BatchMode': 'yes'}
    )

    ssh_agent = PersistentSSHAgent(config=config)

    if ssh_agent.setup_ssh('github.com'):
        print("✅ SSH agent 启动成功")
        return True

    raise RuntimeError("SSH agent 启动失败")
```

### Git 集成

```python
from git import Repo
from persistent_ssh_agent import PersistentSSHAgent
import os

def clone_repo(repo_url: str, local_path: str) -> Repo:
    """使用持久化 SSH 认证克隆仓库。"""
    ssh_agent = PersistentSSHAgent()

    # 提取主机名并设置 SSH
    hostname = ssh_agent._extract_hostname(repo_url)
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
        env=env
    )
```

### 安全特性

1. **SSH 密钥管理**：
   - 自动检测和加载 SSH 密钥（Ed25519、ECDSA、RSA）
   - 支持密钥内容注入（适用于 CI/CD）
   - 安全的密钥文件权限处理
   - 可选的密码短语支持

2. **配置安全**：
   - 严格的主机名验证
   - 安全的默认设置
   - 支持安全相关的 SSH 选项

3. **会话管理**：
   - 安全的代理信息存储
   - 平台特定的安全措施
   - 自动清理过期会话
   - 跨平台兼容性

### 类型提示支持

该库为所有公共接口提供全面的类型提示：

```python
from typing import Optional
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

def setup_ssh(hostname: str, key_file: Optional[str] = None) -> bool:
    config = SSHConfig(identity_file=key_file)
    agent = PersistentSSHAgent(config=config)
    return agent.setup_ssh(hostname)
```

## 🔧 常见使用场景

### 命令行界面 (CLI)

该库提供了一个命令行界面，用于轻松配置和测试：

```bash
# 使用特定身份文件配置 SSH agent
uvx persistent_ssh_agent config --identity-file ~/.ssh/id_ed25519 --prompt-passphrase

# 测试到主机的 SSH 连接
uvx persistent_ssh_agent test github.com

# 列出已配置的 SSH 密钥
uvx persistent_ssh_agent list

# 删除特定的 SSH 密钥
uvx persistent_ssh_agent remove --name github

# 将配置导出到文件
uvx persistent_ssh_agent export --output ~/.ssh/config.json

# 从文件导入配置
uvx persistent_ssh_agent import ~/.ssh/config.json
```

可用命令：

- `config`：配置 SSH agent 设置
  - `--identity-file`：SSH 身份文件路径
  - `--passphrase`：SSH 密钥密码短语（不推荐，请使用 --prompt 代替）
  - `--prompt-passphrase`：提示输入 SSH 密钥密码短语
  - `--expiration`：过期时间（小时）
  - `--reuse-agent`：是否复用现有的 SSH agent

- `test`：测试到主机的 SSH 连接
  - `hostname`：要测试连接的主机名
  - `--identity-file`：SSH 身份文件路径（覆盖配置）
  - `--expiration`：过期时间（小时）（覆盖配置）
  - `--reuse-agent`：是否复用现有的 SSH agent（覆盖配置）
  - `--verbose`：启用详细输出

- `list`：列出已配置的 SSH 密钥

- `remove`：删除已配置的 SSH 密钥
  - `--name`：要删除的密钥名称
  - `--all`：删除所有密钥

- `export`：导出配置
  - `--output`：输出文件路径
  - `--include-sensitive`：在导出中包含敏感信息

- `import`：导入配置
  - `input`：输入文件路径

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

### SSH 配置验证

该库提供全面的 SSH 配置验证功能，支持：

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

# 创建带验证的自定义 SSH 配置
config = SSHConfig()

# 添加包含各种选项的主机配置
config.add_host_config('github.com', {
    # 连接设置
    'IdentityFile': '~/.ssh/github_key',
    'User': 'git',
    'Port': '22',

    # 安全设置
    'StrictHostKeyChecking': 'yes',
    'PasswordAuthentication': 'no',
    'PubkeyAuthentication': 'yes',

    # 连接优化
    'Compression': 'yes',
    'ServerAliveInterval': '60',
    'ServerAliveCountMax': '3',

    # 代理和转发
    'ForwardAgent': 'yes'
})

# 使用经过验证的配置初始化
ssh_agent = PersistentSSHAgent(config=config)
```

支持的配置类别：
- **连接设置**：端口、主机名、用户、身份文件
- **安全设置**：严格主机密钥检查、批处理模式、密码认证
- **连接优化**：压缩、连接超时、服务器保活间隔
- **代理和转发**：代理命令、代理转发、X11转发
- **环境设置**：TTY请求、环境变量发送
- **多路复用选项**：控制主机、控制路径、控制持久化

详细的验证规则和支持的选项，请参见 [SSH 配置验证](docs/ssh_config_validation.md)

### 多主机配置

配置多个主机的 SSH：

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

# 创建带有通用选项的配置
config = SSHConfig(
    ssh_options={
        'BatchMode': 'yes',
        'StrictHostKeyChecking': 'yes',
        'ServerAliveInterval': '60'
    }
)

# 初始化代理
agent = PersistentSSHAgent(config=config)

# 为多个主机设置 SSH
hosts = ['github.com', 'gitlab.com', 'bitbucket.org']
for host in hosts:
    if agent.setup_ssh(host):
        print(f"✅ SSH 已为 {host} 配置完成")
    else:
        print(f"❌ {host} 的 SSH 配置失败")
```

### 全局 SSH 配置

设置全局 SSH 选项：

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

# 创建带有全局选项的配置
config = SSHConfig(
    # 设置身份文件（可选）
    identity_file='~/.ssh/id_ed25519',

    # 设置全局 SSH 选项
    ssh_options={
        'StrictHostKeyChecking': 'yes',
        'PasswordAuthentication': 'no',
        'PubkeyAuthentication': 'yes',
        'BatchMode': 'yes',
        'ConnectTimeout': '30'
    }
)

# 使用全局配置初始化代理
agent = PersistentSSHAgent(config=config)
```

### 密钥管理

该库基于您的 SSH 配置自动管理 SSH 密钥：

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

# 使用指定的密钥
config = SSHConfig(identity_file='~/.ssh/id_ed25519')
agent = PersistentSSHAgent(config=config)

# 或让库自动检测并使用可用的密钥
agent = PersistentSSHAgent()
if agent.setup_ssh('github.com'):
    print("✅ SSH 密钥已加载并就绪！")
```

该库支持以下密钥类型（按优先级排序）：
- Ed25519（推荐，最安全）
- ECDSA
- 带安全密钥的 ECDSA
- 带安全密钥的 Ed25519
- RSA
- DSA（传统，不推荐）

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

## 🤝 贡献

欢迎贡献！请随时提交 Pull Request。

1. Fork 仓库
2. 创建您的功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m '添加了一个惊人的功能'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开一个 Pull Request

## 📄 许可

本项目使用 MIT 许可证 - 请参阅 [LICENSE](LICENSE) 文件以获取详细信息。
