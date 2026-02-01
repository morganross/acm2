import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

PLUGIN_DIR = '/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin'

commands = [
    # Check if tsc is available locally
    f'ls -la {PLUGIN_DIR}/ui/node_modules/.bin/tsc',
    
    # Build using npx (uses local tsc)
    f'sudo -u bitnami bash -c "cd {PLUGIN_DIR}/ui && npx tsc && npx vite build"',
    
    # List the build output
    f'ls -la {PLUGIN_DIR}/assets/react-build/',
    f'ls -la {PLUGIN_DIR}/assets/react-build/assets/ 2>/dev/null || echo "No assets subfolder"',
]

for cmd in commands:
    print(f"\n{'='*60}")
    print(f"$ {cmd[:100]}..." if len(cmd) > 100 else f"$ {cmd}")
    print('='*60)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=600)  # 10 min timeout
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out[:3000])
    if err:
        print(f"STDERR: {err[:2000]}")

ssh.close()
print("\n\nDone!")
