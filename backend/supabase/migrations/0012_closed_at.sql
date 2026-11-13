-- Cierre explícito. Una ficha sin plazo no caduca sola: hace falta esta marca
-- cuando la página dice que cerró, o cuando Find a Tender manda tenderCancellation.

alter table opportunities add column if not exists closed_at timestamptz;
