<?php
/**
 * User Synchronization Class - UUID Version
 *
 * Synchronizes WordPress users with ACM2 backend using UUIDs.
 * Each WordPress user gets a unique UUID that is used for all ACM2 identification.
 * We never send wordpress_user_id to the backend - only uuid and email.
 *
 * Backend URL can be overridden via ACM2_BACKEND_URL constant for two-node deployment.
 * Authentication: Uses X-ACM2-Plugin-Secret header to authorize user creation.
 */

class ACM2_User_Sync {

    /**
     * Get ACM2 API URL - configurable via constant for production
     */
    private static function get_api_url() {
        $backend_url = defined('ACM2_BACKEND_URL') ? ACM2_BACKEND_URL : 'http://127.0.0.1:8000';
        return $backend_url . '/api/v1';
    }

    /**
     * Get or create a UUID for a WordPress user
     * UUIDs are stored in user meta and never change
     */
    public static function get_or_create_user_uuid($user_id) {
        $uuid = get_user_meta($user_id, 'acm2_user_uuid', true);
        if (empty($uuid)) {
            // Generate a new UUID v4
            $uuid = sprintf('%04x%04x-%04x-%04x-%04x-%04x%04x%04x',
                mt_rand(0, 0xffff), mt_rand(0, 0xffff),
                mt_rand(0, 0xffff),
                mt_rand(0, 0x0fff) | 0x4000,
                mt_rand(0, 0x3fff) | 0x8000,
                mt_rand(0, 0xffff), mt_rand(0, 0xffff), mt_rand(0, 0xffff)
            );
            update_user_meta($user_id, 'acm2_user_uuid', $uuid);
            error_log('ACM2 User Sync: Generated new UUID ' . $uuid . ' for WP user ' . $user_id);
        }
        return $uuid;
    }

    /**
     * Initialize synchronization hooks
     */
    public static function init() {
        add_action('user_register', [__CLASS__, 'sync_new_user']);
        add_action('delete_user', [__CLASS__, 'delete_acm2_user']);
        add_action('wp_ajax_acm2_sync_all_users', [__CLASS__, 'ajax_sync_all_users']);
        error_log('[ACM2_SYNC] init() - Hooks registered');
    }

    /**
     * Sync WordPress user to ACM2 backend using UUID
     */
    public static function sync_new_user($user_id) {
        $user = get_userdata($user_id);
        if (!$user) {
            error_log('ACM2 User Sync Error: Cannot get user data for user_id=' . $user_id);
            return;
        }

        // Get or create UUID for this user
        $uuid = self::get_or_create_user_uuid($user_id);
        error_log('ACM2 User Sync: Syncing user UUID ' . $uuid . ' (WP ID: ' . $user_id . ')');

        // Check if user already has API key
        $existing_key = acm2_get_user_api_key($user_id);
        if ($existing_key) {
            error_log('ACM2 User Sync: User already has API key, skipping sync');
            return;
        }

        // Get plugin secret for authentication
        $plugin_secret = acm2_get_plugin_secret();
        if (empty($plugin_secret)) {
            error_log('ACM2 User Sync Error: Admin API key not configured');
            return;
        }

        $api_url = self::get_api_url() . '/users';

        // Build headers with plugin secret
        $headers = [
            'Content-Type' => 'application/json',
            'X-ACM2-Plugin-Secret' => $plugin_secret,
        ];

        // Send ONLY uuid and email - no wordpress_user_id
        $body_data = [
            'uuid' => $uuid,
            'email' => $user->user_email,
        ];

        $response = wp_remote_post($api_url, [
            'timeout' => 30,
            'headers' => $headers,
            'body' => json_encode($body_data),
            'sslverify' => false,
        ]);

        if (is_wp_error($response)) {
            error_log('ACM2 User Sync Error: ' . $response->get_error_message());
            return;
        }

        $status_code = wp_remote_retrieve_response_code($response);
        $body = json_decode(wp_remote_retrieve_body($response), true);

        if ($status_code >= 200 && $status_code < 300 && isset($body['api_key'])) {
            acm2_save_user_api_key($user_id, $body['api_key']);
            error_log('ACM2 User Sync: API key saved for UUID ' . $uuid);
        } else {
            $error = isset($body['detail']) ? $body['detail'] : 'Unknown error';
            error_log('ACM2 User Sync Error: Status ' . $status_code . ' - ' . $error);
        }
    }

    /**
     * Delete ACM2 user when WordPress user is deleted
     */
    public static function delete_acm2_user($user_id) {
        $api_key = acm2_get_user_api_key($user_id);
        if (!$api_key) {
            return;
        }

        global $wpdb;
        $table_name = $wpdb->prefix . 'acm2_api_keys';
        $wpdb->delete($table_name, ['wp_user_id' => $user_id], ['%d']);
        delete_user_meta($user_id, 'acm2_user_id');
        delete_user_meta($user_id, 'acm2_user_uuid');
    }

    /**
     * AJAX handler to sync all existing WordPress users
     */
    public static function ajax_sync_all_users() {
        if (!wp_verify_nonce($_POST['_wpnonce'] ?? '', 'acm2_sync_users')) {
            wp_send_json_error('Invalid security token');
            return;
        }

        if (!current_user_can('manage_options')) {
            wp_send_json_error('Insufficient permissions');
            return;
        }

        $users = get_users(['fields' => 'ID']);
        $synced = 0;
        $skipped = 0;
        $failed = 0;

        foreach ($users as $user_id) {
            $existing = acm2_get_user_api_key($user_id);
            if ($existing) {
                $skipped++;
                continue;
            }

            self::sync_new_user($user_id);
            
            if (acm2_get_user_api_key($user_id)) {
                $synced++;
            } else {
                $failed++;
            }
        }

        wp_send_json_success([
            'message' => "Synced {$synced} users. Failed: {$failed}. Skipped: {$skipped} (already synced)"
        ]);
    }
}
