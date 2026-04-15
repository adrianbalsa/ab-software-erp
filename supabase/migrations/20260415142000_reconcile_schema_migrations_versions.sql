-- Reconcile migration versions against local files
-- Use only after validating production schema is already at desired state.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000000') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000000', '20260319000000_fiscal_immutability_soft_delete_snapshot', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000001') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000001', '20260319000001_gastos_fiscal_verifactu', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000002') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000002', '20260319000002_facturas_verifactu_f1', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000003') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000003', '20260319000003_auditoria_api_columns_facturas_immutability', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000004') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000004', '20260319000004_refresh_tokens', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000005') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000005', '20260319000005_facturas_rectificativas_r1', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000006') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000006', '20260319000006_rename_columns_legacy_to_api', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000007') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000007', '20260319000007_esg_certificacion_vw_emissions', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000008') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000008', '20260319000008_refresh_tokens_ip_user_agent', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000009') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000009', '20260319000009_rls_tenant_current_empresa', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000010') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000010', '20260319000010_pii_widen_nif_ferrnet_columns', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000011') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000011', '20260319000011_rls_granular_profiles_empresa_id_lock', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000012') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000012', '20260319000012_add_gocardless_to_profiles', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000013') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000013', '20260319000013_flota_vencimientos_alertas', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000014') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000014', '20260319000014_master_soft_delete_clientes_empresas', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000015') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000015', '20260319000015_bank_sync_gocardless', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000016') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000016', '20260319000016_normativa_euro_flota_vehiculos', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000017') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000017', '20260319000017_portes_co2_emitido_esg', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000018') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000018', '20260319000018_webhooks_hmac_endpoints_developer', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000019') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000019', '20260319000019_empresas_stripe_billing', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000020') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000020', '20260319000020_user_accounts_mfa', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000021') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000021', '20260319000021_facturas_xml_verifactu', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000022') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000022', '20260319000022_esg_and_queues', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000023') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000023', '20260319000023_esg_dynamic_co2_empty_km', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000024') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000024', '20260319000024_facturas_qr_content', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000025') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000025', '20260319000025_finance_snapshots', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000026') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000026', '20260319000026_maps_distance_cache', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000027') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000027', '20260319000027_verifactu_huella_chain', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000028') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000028', '20260319000028_esg_flota_porte_vehiculo', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000029') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000029', '20260319000029_bank_integration', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000030') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000030', '20260319000030_infra_health_logs', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000031') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000031', '20260319000031_portes_activos_math_engine_view', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000032') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000032', '20260319000032_rbac_user_role_profiles_portes_rls', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000033') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000033', '20260319000033_bank_accounts_transactions_open_banking', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000034') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000034', '20260319000034_bank_accounts_transactions_open_banking', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000035') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000035', '20260319000035_audit_logs_triggers', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000036') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000036', '20260319000036_verifactu_fingerprint_finalizacion', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000037') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000037', '20260319000037_aeat_verifactu_envios', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000038') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000038', '20260319000038_webhooks_rate_limit', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000039') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000039', '20260319000039_vehiculos_gps_ultima', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000040') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000040', '20260319000040_movimientos_bancarios', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000041') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000041', '20260319000041_treasury_vencimientos', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000042') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000042', '20260319000042_portes_cmr_conductor', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000043') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000043', '20260319000043_clientes_cuenta_contable', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000044') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000044', '20260319000044_portes_firma_entrega_pod', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000045') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000045', '20260319000045_fix_rls_leaks', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000046') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000046', '20260319000046_gastos_vehiculo_import', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000047') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000047', '20260319000047_esg_auditoria_fuel_import', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000048') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000048', '20260319000048_audit_logs_append_only_security', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000049') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000049', '20260319000049_audit_logs_select_strict_admin', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000050') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000050', '20260319000050_webhooks_b2b', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000051') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000051', '20260319000051_fleet_maintenance', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000052') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000052', '20260319000052_schema_sync_esg_treasury_pod_gin', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000053') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000053', '20260319000053_flota_fechas_administrativas', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000054') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000054', '20260319000054_portes_dni_consignatario_pod', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000055') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000055', '20260319000055_portal_cliente_rbac', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000056') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000056', '20260319000056_portal_onboarding_risk_acceptance', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000057') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000057', '20260319000057_audit_trail_process_audit_log', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000058') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000058', '20260319000058_add_portes_co2_kg', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000059') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000059', '20260319000059_facturas_fingerprint_hash_chain', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000100') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000100', '20260319000100_rls_jwt_strict_multi_tenant', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000101') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000101', '20260319000101_rbac_admin_staff_extension', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000103') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000103', '20260319000103_003_esg_factors', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000104') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000104', '20260319000104_004_consolidated_rbac_rls', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000105') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000105', '20260319000105_audit_rls_status', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000106') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000106', '20260319000106_rbac_setup', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260319000107') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260319000107', '20260319000107_verifactu_logic', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260414120000') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260414120000', '20260414120000_geo_cache_and_portes_coords', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260414130000') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260414130000', '20260414130000_esg_co2_module', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260415130000') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260415130000', '20260415130000_audit_security_fixes', ARRAY[]::text[]);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM supabase_migrations.schema_migrations WHERE version = '20260614000000') THEN
    INSERT INTO supabase_migrations.schema_migrations(version, name, statements) VALUES ('20260614000000', '20260614000000_auth_autonomous_onboarding', ARRAY[]::text[]);
  END IF;
END
$$;