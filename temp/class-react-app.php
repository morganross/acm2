<?php
/**
 * React App Integration Class
 *
 * Loads the React frontend in WordPress admin pages.
 */

class ACM2_React_App {

    /**
     * Initialize the React app integration
     */
    public static function init() {
        add_action('admin_menu', [__CLASS__, 'add_admin_pages']);
        add_action('admin_enqueue_scripts', [__CLASS__, 'enqueue_react_app']);
    }

    /**
     * Add admin menu pages
     */
    public static function add_admin_pages() {
        // Add "Runs" submenu under ACM2 (this is where the React app loads)
        add_submenu_page(
            'acm2-settings',   // Parent slug
            'ACM2 App',        // Page title
            'App',             // Menu title
            'manage_options',  // Capability
            'acm2-app',        // Menu slug
            [__CLASS__, 'render_app_page']
        );
    }

    /**
     * Enqueue React app scripts and styles
     */
    public static function enqueue_react_app($hook) {
        // Only load on ACM2 app page
        if (strpos($hook, 'acm2-app') === false) {
            return;
        }

        error_log('ACM2_React_App: enqueue_react_app() - Loading React app for hook=' . $hook);

        $build_dir = ACM2_PLUGIN_DIR . 'assets/react-build/';
        $build_url = ACM2_PLUGIN_URL . 'assets/react-build/';

        error_log('ACM2_React_App: Build directory=' . $build_dir);

        // Check for build files - support both hashed (index-*.js) and non-hashed (acm2-app.js) filenames
        $js_file = null;
        $css_file = null;

        // First try non-hashed names (current vite config)
        if (file_exists($build_dir . 'acm2-app.js')) {
            $js_file = 'acm2-app.js';
            error_log('ACM2_React_App: Found acm2-app.js');
        }
        if (file_exists($build_dir . 'acm2-app.css')) {
            $css_file = 'acm2-app.css';
            error_log('ACM2_React_App: Found acm2-app.css');
        }

        // Fallback to hashed names in assets/ subfolder (legacy)
        if (!$js_file) {
            $js_files = glob($build_dir . 'assets/index-*.js');
            if (!empty($js_files)) {
                $js_file = 'assets/' . basename($js_files[0]);
                error_log('ACM2_React_App: Found legacy JS: ' . $js_file);
            }
        }
        if (!$css_file) {
            $css_files = glob($build_dir . 'assets/index-*.css');
            if (!empty($css_files)) {
                $css_file = 'assets/' . basename($css_files[0]);
                error_log('ACM2_React_App: Found legacy CSS: ' . $css_file);
            }
        }

        if (!$js_file || !$css_file) {
            error_log('ACM2_React_App: ERROR - Build files not found! Run: cd react-app && npm run build');
            error_log('ACM2_React_App: Looked in: ' . $build_dir);
            return;
        }

        // CACHE BUSTER: Use current timestamp to GUARANTEE no caching
        // This is intentionally aggressive - caching has caused years of bugs
        $cache_bust = time();
        $js_full_path = $build_dir . $js_file;
        $css_full_path = $build_dir . $css_file;

        // Enqueue React app CSS with aggressive cache busting
        wp_enqueue_style(
            'acm2-react-app',
            $build_url . $css_file,
            [],
            filemtime($css_full_path) . '.' . $cache_bust
        );

        // Enqueue React app JS with aggressive cache busting
        wp_enqueue_script(
            'acm2-react-app',
            $build_url . $js_file,
            [],
            filemtime($js_full_path) . '.' . $cache_bust,
            true
        );

        // Add type="module" to script tag
        add_filter('script_loader_tag', function($tag, $handle) {
            if ($handle === 'acm2-react-app') {
                return str_replace(' src', ' type="module" src', $tag);
            }
            return $tag;
        }, 10, 2);

        // Get the user's ACM2 API key (decrypted from database)
        $current_user_id = get_current_user_id();
        $acm2_api_key = function_exists('acm2_get_user_api_key') ? acm2_get_user_api_key($current_user_id) : '';

        // Get user UUID for backend identification
        $user_uuid = function_exists('acm2_get_user_uuid') ? acm2_get_user_uuid($current_user_id) : '';

        // Backend URL - can be overridden via constant for two-node deployment
        $backend_url = defined('ACM2_BACKEND_URL') ? ACM2_BACKEND_URL : 'http://127.0.0.1:8000';

        error_log('ACM2_React_App: Config for user_id=' . $current_user_id);
        error_log('ACM2_React_App: Backend URL=' . $backend_url);
        error_log('ACM2_React_App: User UUID=' . $user_uuid);
        error_log('ACM2_React_App: API key available=' . (!empty($acm2_api_key) ? 'YES (first 10: ' . substr($acm2_api_key, 0, 10) . '...)' : 'NO'));

        // Pass config to React app
        wp_localize_script('acm2-react-app', 'acm2Config', [
            'apiUrl' => $backend_url . '/api/v1',  // Direct to backend API
            'nonce' => wp_create_nonce('wp_rest'),  // Keep for backwards compat
            'currentUser' => wp_get_current_user()->user_login,
            'userUuid' => $user_uuid,  // UUID for backend identification
            'apiKey' => $acm2_api_key,  // ACM2 API key for all authentication (decrypted)
        ]);

        error_log('ACM2_React_App: React app enqueued successfully');
    }

    /**
     * Render the App page - full screen React app
     */
    public static function render_app_page() {
        error_log('ACM2_React_App: render_app_page() called');
        ?>
        <style>
            #wpbody-content { padding: 0 !important; }
            #wpfooter { display: none; }
            .wrap { margin: 0 !important; padding: 0 !important; max-width: none !important; }
            #root {
                min-height: calc(100vh - 32px); /* Account for admin bar */
                background: #0f172a; /* Match your app's dark background */
            }
        </style>
        <div class="wrap">
            <div id="root"></div>
        </div>
        <?php
    }
}
