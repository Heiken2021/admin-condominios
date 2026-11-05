CREATE TABLE IF NOT EXISTS unidades (
 id BIGSERIAL PRIMARY KEY, unidad VARCHAR(50) UNIQUE NOT NULL,
 propietario VARCHAR(200), inquilino VARCHAR(200), telefono VARCHAR(50), email VARCHAR(254),
 cuota_base NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (cuota_base >= 0),
 recargo_pct NUMERIC(6,2) NOT NULL DEFAULT 0 CHECK (recargo_pct BETWEEN 0 AND 100),
 activo BOOLEAN NOT NULL DEFAULT TRUE, creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS usuarios (
 id BIGSERIAL PRIMARY KEY, username VARCHAR(100) UNIQUE NOT NULL, nombre VARCHAR(200) NOT NULL,
 email VARCHAR(254), rol VARCHAR(20) NOT NULL CHECK (rol IN ('admin','residente')),
 unidad_id BIGINT REFERENCES unidades(id) ON DELETE SET NULL,
 salt TEXT NOT NULL, password_hash TEXT NOT NULL, activo BOOLEAN NOT NULL DEFAULT TRUE,
 reset_token_hash TEXT, reset_expira TIMESTAMPTZ, creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS cargos (
 id BIGSERIAL PRIMARY KEY, unidad_id BIGINT NOT NULL REFERENCES unidades(id) ON DELETE RESTRICT,
 periodo VARCHAR(7) NOT NULL, concepto VARCHAR(200) NOT NULL DEFAULT 'Cuota de mantenimiento',
 monto NUMERIC(12,2) NOT NULL CHECK (monto >= 0), vencimiento DATE,
 recargo NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (recargo >= 0), creado_en TIMESTAMPTZ DEFAULT NOW(),
 UNIQUE(unidad_id, periodo, concepto)
);
CREATE TABLE IF NOT EXISTS pagos (
 id BIGSERIAL PRIMARY KEY, unidad_id BIGINT NOT NULL REFERENCES unidades(id) ON DELETE RESTRICT,
 periodo VARCHAR(7), fecha DATE NOT NULL, monto NUMERIC(12,2) NOT NULL CHECK (monto > 0),
 metodo VARCHAR(50), referencia VARCHAR(200), notas TEXT, comprobante_url TEXT,
 creado_por BIGINT REFERENCES usuarios(id) ON DELETE SET NULL, creado_en TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS gastos (
 id BIGSERIAL PRIMARY KEY, fecha DATE NOT NULL, categoria VARCHAR(100) NOT NULL,
 concepto VARCHAR(250) NOT NULL, proveedor VARCHAR(200), monto NUMERIC(12,2) NOT NULL CHECK (monto > 0),
 referencia VARCHAR(200), notas TEXT, comprobante_url TEXT,
 creado_por BIGINT REFERENCES usuarios(id) ON DELETE SET NULL, creado_en TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS auditoria (
 id BIGSERIAL PRIMARY KEY, fecha TIMESTAMPTZ NOT NULL DEFAULT NOW(), usuario_id BIGINT,
 username VARCHAR(100), accion VARCHAR(100) NOT NULL, detalle TEXT, ip_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_cargos_unidad_periodo ON cargos(unidad_id, periodo);
CREATE INDEX IF NOT EXISTS idx_pagos_unidad_fecha ON pagos(unidad_id, fecha);
CREATE INDEX IF NOT EXISTS idx_gastos_fecha ON gastos(fecha);
CREATE INDEX IF NOT EXISTS idx_auditoria_fecha ON auditoria(fecha DESC);
