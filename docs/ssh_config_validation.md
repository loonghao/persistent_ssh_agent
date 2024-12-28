# SSH Configuration Validation

This document describes the validation rules for SSH configuration options in the persistent-ssh-agent package.

## Connection Settings

### Port

- Valid range: 1-65535
- Example: `Port 22`

### Hostname

- Any valid hostname or IP address
- Example: `Hostname github.com`

### User

- Any valid username
- Example: `User git`

### IdentityFile

- Valid file path
- Can have multiple entries
- Example: `IdentityFile ~/.ssh/id_rsa`

## Security Settings

### StrictHostKeyChecking

- Valid options: yes, no, accept-new, off, ask
- Example: `StrictHostKeyChecking yes`

### BatchMode

- Valid options: yes, no
- Example: `BatchMode yes`

### PasswordAuthentication

- Valid options: yes, no
- Example: `PasswordAuthentication no`

### PubkeyAuthentication

- Valid options: yes, no
- Example: `PubkeyAuthentication yes`

## Connection Optimization

### Compression

- Valid options: yes, no
- Example: `Compression yes`

### ConnectTimeout

- Non-negative integer
- Example: `ConnectTimeout 30`

### ServerAliveInterval

- Non-negative integer
- Example: `ServerAliveInterval 60`

### ServerAliveCountMax

- Non-negative integer
- Example: `ServerAliveCountMax 3`

## Proxy and Forwarding

### ProxyCommand

- Any valid command string
- Example: `ProxyCommand ssh -W %h:%p jumphost`

### ForwardAgent

- Valid options: yes, no
- Example: `ForwardAgent yes`

### ForwardX11

- Valid options: yes, no
- Example: `ForwardX11 no`

## Environment Settings

### RequestTTY

- Valid options: yes, no, force, auto
- Example: `RequestTTY auto`

### SendEnv

- Any valid environment variable pattern
- Can have multiple entries
- Example: `SendEnv LANG LC_*`

## Multiplexing

### ControlMaster

- Valid options: yes, no, ask, auto, autoask
- Example: `ControlMaster auto`

### ControlPath

- Valid file path
- Example: `ControlPath ~/.ssh/cm-%r@%h:%p`

### ControlPersist

- Valid options: yes, no, or time duration in seconds
- Example: `ControlPersist 1h`

## Canonicalization

### CanonicalizeHostname

- Valid options: yes, no, always
- Example: `CanonicalizeHostname yes`

### CanonicalizeMaxDots

- Non-negative integer
- Example: `CanonicalizeMaxDots 1`

### CanonicalizeDomains

- List of domain names
- Example: `CanonicalizeDomains example.com example.net`

## Error Handling

The configuration parser will:
1. Skip invalid configuration keys
2. Log warnings for invalid values
3. Use default values when invalid values are provided
4. Validate all values before applying them

## Best Practices

1. Always use the most restrictive security settings appropriate for your use case
2. Set appropriate timeouts to prevent hanging connections
3. Use multiplexing when making multiple connections to the same host
4. Enable compression for slow connections
5. Use canonical hostnames when working with complex network setups
