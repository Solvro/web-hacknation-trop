-- 0010 · artifact roles seen in DANE: phone screenshots, screen recordings, yt-dlp ad info, third-party
--        capture manifests ("page-capture" tool), and funnel step pages.

ALTER TABLE artifact_refs DROP CONSTRAINT IF EXISTS artifact_refs_role_check;
ALTER TABLE artifact_refs ADD CONSTRAINT artifact_refs_role_check CHECK (role IN (
    'ad_screenshot','ad_creative_image','ad_creative_video','ad_info_json',
    'landing_har','landing_html_source','landing_html_rendered','landing_html_saved',
    'landing_screenshot_full','landing_screenshot_viewport','landing_pdf','landing_mhtml',
    'landing_text','landing_video','favicon','asset_image','asset_script','media_video',
    'media_audio','storage_cookies','storage_local','storage_session','dns_ssl_json',
    'metadata_json','archive_info_json','capture_manifest','sha256_manifest','bundle_zip',
    'device_screenshot','screen_recording','note','other'));

INSERT INTO schema_migrations(version) VALUES ('0010_dane_roles') ON CONFLICT DO NOTHING;
