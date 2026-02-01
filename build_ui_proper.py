import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

PLUGIN_DIR = '/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin'

commands = [
    # Fix permissions on ui folder
    f'sudo chown -R bitnami:bitnami {PLUGIN_DIR}/ui',
    
    # Update vite.config.ts as bitnami user
    f'''sudo -u bitnami bash -c "cat > {PLUGIN_DIR}/ui/vite.config.ts << 'EOFCONFIG'
import {{ defineConfig }} from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({{
  plugins: [react()],
  resolve: {{
    alias: {{
      '@': path.resolve(__dirname, './src'),
    }},
  }},
  base: './',
  build: {{
    outDir: '../assets/react-build',
    emptyOutDir: true,
    rollupOptions: {{
      output: {{
        entryFileNames: 'assets/index-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]'
      }}
    }}
  }},
}})
EOFCONFIG"''',

    # Verify vite.config.ts
    f'cat {PLUGIN_DIR}/ui/vite.config.ts',
    
    # Install npm dependencies as bitnami
    f'sudo -u bitnami bash -c "cd {PLUGIN_DIR}/ui && npm install"',
    
    # Build the UI as bitnami
    f'sudo -u bitnami bash -c "cd {PLUGIN_DIR}/ui && npm run build"',
    
    # List the build output
    f'ls -la {PLUGIN_DIR}/assets/react-build/',
    f'ls -la {PLUGIN_DIR}/assets/react-build/assets/',
]

for cmd in commands:
    print(f"\n{'='*60}")
    print(f"$ {cmd[:100]}..." if len(cmd) > 100 else f"$ {cmd}")
    print('='*60)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out[:3000])
        if len(out) > 3000:
            print(f"... (truncated)")
    if err:
        print(f"STDERR: {err[:2000]}")

ssh.close()
print("\n\nDone!")
