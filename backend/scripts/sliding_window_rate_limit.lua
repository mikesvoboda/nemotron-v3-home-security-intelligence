-- Sliding window rate limiting script
-- Implements atomic rate limiting using Redis sorted sets
--
-- This script ensures atomicity that cannot be achieved with Redis pipelines.
-- The check-and-increment operation happens in a single atomic step,
-- preventing race conditions where multiple concurrent requests might
-- all pass the count check before any of them increment the counter.
--
-- KEYS[1] = rate limit key (e.g., "rate_limit:default:192.168.1.100")
-- ARGV[1] = current timestamp (float, e.g., 1706012345.123456)
-- ARGV[2] = window size in seconds (int, e.g., 60)
-- ARGV[3] = rate limit (int, e.g., 100)
--
-- Returns: {allowed (0 or 1), current_count}
--   allowed = 1 if request is allowed, 0 if denied
--   current_count = number of requests in current window (after this request if allowed)

local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

-- Remove entries outside the sliding window
local window_start = now - window
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

-- Count current requests in window
local count = redis.call('ZCARD', key)

if count < limit then
    -- Under limit: add this request and set expiry
    -- Use timestamp as both score and member (member includes nanoseconds for uniqueness)
    redis.call('ZADD', key, now, tostring(now))
    redis.call('EXPIRE', key, window + 10)
    return {1, count + 1}  -- allowed, new count
else
    -- Over limit: deny request
    -- Still set expiry to clean up the key eventually
    redis.call('EXPIRE', key, window + 10)
    return {0, count}  -- denied, current count
end
