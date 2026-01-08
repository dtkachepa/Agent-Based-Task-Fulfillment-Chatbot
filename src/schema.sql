PRAGMA foreign_keys = ON;

-- USERS
CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY,
  name TEXT NOT NULL
);

-- WALLET (1:1 with users)
CREATE TABLE IF NOT EXISTS wallets (
  user_id TEXT PRIMARY KEY,
  balance_cents INTEGER NOT NULL CHECK (balance_cents >= 0),
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- PRODUCTS
CREATE TABLE IF NOT EXISTS products (
  product_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
  inventory INTEGER NOT NULL CHECK (inventory >= 0)
);

-- ORDERS
CREATE TABLE IF NOT EXISTS orders (
  order_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL,           -- e.g. "PLACED", "CANCELLED", "REFUNDED"
  total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- ORDER ITEMS
CREATE TABLE IF NOT EXISTS order_items (
  order_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
  FOREIGN KEY (order_id) REFERENCES orders(order_id),
  FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- LEDGER (audit log + idempotency)
CREATE TABLE IF NOT EXISTS ledger (
  tx_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  kind TEXT NOT NULL,             -- "TOPUP" | "PURCHASE" | "REFUND" etc.
  amount_cents INTEGER NOT NULL,  -- positive or negative depending on kind
  created_at TEXT NOT NULL,
  client_request_id TEXT UNIQUE,  -- idempotency key for external requests
  metadata_json TEXT,
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_orders_user_time ON orders(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ledger_user_time ON ledger(user_id, created_at);
