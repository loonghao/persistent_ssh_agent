概述
====

persistent_ssh_agent 是一个帮助管理 SSH agent 会话持久化的 Python 包。

特性
----

- 自动 SSH agent 管理
- 会话持久化
- 跨平台支持
- 简单配置

安装
----

你可以使用 pip 安装 persistent_ssh_agent：

.. code-block:: bash

   pip install persistent_ssh_agent

使用方法
-------

基本用法：

.. code-block:: python

   from persistent_ssh_agent import SSHAgent

   # 初始化 agent
   agent = SSHAgent()

   # 启动 agent
   agent.start()

   # 添加你的 SSH 密钥
   agent.add_key('path/to/your/key')

   # agent 将在会话之间保持持久化

配置
----

你可以通过以下方式配置 agent 行为：

1. 环境变量
2. 配置文件
3. 直接参数

查看文档获取详细的配置选项。
