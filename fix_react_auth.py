import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

PLUGIN_DIR = '/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin'

commands = [
    # Update client.ts on frontend
    f'sudo -u bitnami cat > {PLUGIN_DIR}/ui/src/api/client.ts << \'ENDOFFILE\'\n' + open('C:/devlop/acm2/acm2/ui/src/api/client.ts').read() + '\nENDOFFILE',
]

# First, upload the updated client.ts
print("Uploading updated client.ts...")
sftp = ssh.open_sftp()
sftp.put('C:/devlop/acm2/acm2/ui/src/api/client.ts', '/tmp/client.ts')
sftp.close()

commands = [
    # Copy client.ts to plugin
    f'sudo cp /tmp/client.ts {PLUGIN_DIR}/ui/src/api/client.ts',
    f'sudo chown bitnami:bitnami {PLUGIN_DIR}/ui/src/api/client.ts',
    
    # Rebuild UI
    f'sudo -u bitnami bash -c "cd {PLUGIN_DIR}/ui && npm run build"',
    
    # List build output
    f'ls -la {PLUGIN_DIR}/assets/react-build/assets/',
    
    # Git add, commit, push
    f'sudo -u bitnami git -C {PLUGIN_DIR} add -A',
    f'sudo -u bitnami git -C {PLUGIN_DIR} commit -m "Fix React app auth: use X-ACM2-API-Key header and window.acm2Config"',
    f'sudo -u bitnami git -C {PLUGIN_DIR} push origin main',
]

for cmd in commands:
    print(f"\n{'='*60}")
    print(f"$ {cmd[:80]}..." if len(cmd) > 80 else f"$ {cmd}")
    print('='*60)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out[:2000])
    if err:
        print(f"STDERR: {err[:1000]}")

ssh.close()
print("\n\nDone!")
