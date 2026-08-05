-- =============================================================================
-- Redshiftのテーブル・カラムコメント
-- 全テーブルの作成・データ投入後に適用
-- =============================================================================

-- sensor_readings
COMMENT ON TABLE public.sensor_readings IS 'センサー読取時系列データ - 工場センサーからの定期的な測定値とステータスを記録';
COMMENT ON COLUMN public.sensor_readings.reading_id IS '読取記録の一意識別子';
COMMENT ON COLUMN public.sensor_readings.sensor_id IS '読取を行ったセンサーのID（Glue sensorsテーブルへの外部キー）';
COMMENT ON COLUMN public.sensor_readings.machine_id IS 'センサーが取り付けられている機械のID（Glue machinesテーブルへの外部キー）';
COMMENT ON COLUMN public.sensor_readings.reading_time IS '読取が記録されたタイムスタンプ';
COMMENT ON COLUMN public.sensor_readings.value IS 'センサー固有の単位での測定値';
COMMENT ON COLUMN public.sensor_readings.status IS '読取の分類：正常（normal）、警告（warning）、危険（critical）';

-- production_events
COMMENT ON TABLE public.production_events IS '生産イベントログ - 工場機械の開始/停止、メンテナンス、エラー、校正イベントを記録';
COMMENT ON COLUMN public.production_events.event_id IS 'イベント記録の一意識別子';
COMMENT ON COLUMN public.production_events.machine_id IS 'イベントに関連する機械のID（Glue machinesテーブルへの外部キー）';
COMMENT ON COLUMN public.production_events.event_type IS 'イベント種別：開始（start）、停止（stop）、メンテナンス（maintenance）、エラー（error）、校正（calibration）';
COMMENT ON COLUMN public.production_events.event_time IS 'イベント発生のタイムスタンプ';
COMMENT ON COLUMN public.production_events.duration_minutes IS 'イベントの所要時間（分）（開始/停止などの瞬間的イベントの場合はNULL）';
COMMENT ON COLUMN public.production_events.description IS 'イベントの説明';

-- quality_inspections
COMMENT ON TABLE public.quality_inspections IS '品質検査結果 - 工場の品質チェック記録（合格/不合格/警告の判定と不良数を含む）';
COMMENT ON COLUMN public.quality_inspections.inspection_id IS '検査記録の一意識別子';
COMMENT ON COLUMN public.quality_inspections.machine_id IS '検査対象の機械ID（Glue machinesテーブルへの外部キー）';
COMMENT ON COLUMN public.quality_inspections.inspector_name IS '品質検査を実施した検査員の名前';
COMMENT ON COLUMN public.quality_inspections.inspection_time IS '検査実施のタイムスタンプ';
COMMENT ON COLUMN public.quality_inspections.result IS '検査結果：合格（pass）、不合格（fail）、警告（warning）';
COMMENT ON COLUMN public.quality_inspections.defect_count IS '発見された不良数（合格の場合は0）';
COMMENT ON COLUMN public.quality_inspections.notes IS '検査員による追加メモや所見';
