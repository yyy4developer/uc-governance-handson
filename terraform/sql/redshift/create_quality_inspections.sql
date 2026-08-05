CREATE TABLE IF NOT EXISTS public.quality_inspections (
    inspection_id    INT PRIMARY KEY,
    machine_id       INT NOT NULL,
    inspector_name   VARCHAR(50) NOT NULL,
    inspection_time  TIMESTAMP NOT NULL,
    result           VARCHAR(20) NOT NULL,
    defect_count     INT NOT NULL DEFAULT 0,
    notes            VARCHAR(500)
)
