-- Проверка количества и уникальных сущностей
SELECT COUNT(*) AS events,
       COUNT(DISTINCT user_id) AS users,
       COUNT(DISTINCT product_id) AS products
FROM events;

-- Популярные товары по типу действия
SELECT action, product_id, category, COUNT(*) AS event_count
FROM events
GROUP BY action, product_id, category
ORDER BY action, event_count DESC;

-- Выручка и число покупок по категориям
SELECT category, COUNT(*) AS purchases,
       ROUND(SUM(price), 2) AS revenue
FROM events WHERE action = 'purchase'
GROUP BY category ORDER BY revenue DESC;

-- Последовательная воронка по уникальным парам пользователь–товар.
-- Временные метки хранятся в ISO-формате, поэтому лексикографический порядок совпадает с хронологией.
WITH first_view AS (
  SELECT user_id, product_id, MIN(timestamp) AS view_at
  FROM events WHERE action = 'view' GROUP BY user_id, product_id
), cart_after_view AS (
  SELECT v.user_id, v.product_id, v.view_at, MIN(e.timestamp) AS cart_at
  FROM first_view v JOIN events e USING (user_id, product_id)
  WHERE e.action = 'add_to_cart' AND e.timestamp > v.view_at
  GROUP BY v.user_id, v.product_id, v.view_at
), purchase_after_cart AS (
  SELECT c.user_id, c.product_id
  FROM cart_after_view c JOIN events e USING (user_id, product_id)
  WHERE e.action = 'purchase' AND e.timestamp > c.cart_at
  GROUP BY c.user_id, c.product_id
)
SELECT (SELECT COUNT(*) FROM first_view) AS viewed_pairs,
       (SELECT COUNT(*) FROM cart_after_view) AS carted_after_view_pairs,
       (SELECT COUNT(*) FROM purchase_after_cart) AS purchased_after_cart_pairs,
       ROUND(100.0 * (SELECT COUNT(*) FROM cart_after_view) /
             NULLIF((SELECT COUNT(*) FROM first_view), 0), 2) AS view_to_cart_pct,
       ROUND(100.0 * (SELECT COUNT(*) FROM purchase_after_cart) /
             NULLIF((SELECT COUNT(*) FROM cart_after_view), 0), 2) AS cart_to_purchase_pct,
       ROUND(100.0 * (SELECT COUNT(*) FROM purchase_after_cart) /
             NULLIF((SELECT COUNT(*) FROM first_view), 0), 2) AS view_to_purchase_pct;
