import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

PLUGIN_DIR = '/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin'

commands = [
    # Add node_modules to gitignore if not already
    f'grep -q "node_modules" {PLUGIN_DIR}/.gitignore || echo "ui/node_modules/" | sudo -u bitnami tee -a {PLUGIN_DIR}/.gitignore',
    
    # Git add all changes
    f'sudo -u bitnami git -C {PLUGIN_DIR} add -A',
    
    # Git status
    f'sudo -u bitnami git -C {PLUGIN_DIR} status',
    
    # Git commit
    f'sudo -u bitnami git -C {PLUGIN_DIR} commit -m "Build React UI from source, update vite config"',
    
    # Git push
    f'sudo -u bitnami git -C {PLUGIN_DIR} push origin main',
]

for cmd in commands:
    print(f"\n{'='*60}")
    print(f"$ {cmd[:100]}..." if len(cmd) > 100 else f"$ {cmd}")
    print('='*60)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out[:2000])
    if err:
        print(f"STDERR: {err[:1000]}")

ssh.close()
print("\n\nDone!")
