-- Nemori Engine Test File — SQL
-- Tests every engine feature that applies to SQL code.
--
-- Features tested:
--   L1a   minify: strip_inline_comments, collapse_blank_lines, strip_indentation
--   L1b   @m substitution: frequency-ordered aliases
--   L1d   @t type aliases: VT, CT, DT, TS, CS, JC, IX, FK, PK, UV
--   Item8 @b block dedup: identical subqueries

-- =====================================================================
-- SECTION 1: @t Type Alias Candidates (SQL)
-- =====================================================================
-- SQL @t table: VT=VARCHAR, CT=CHAR, DT=DATETIME, TS=TIMESTAMP,
-- CS=CURSOR, JC=JOIN, IX=INDEX, FK=FOREIGN KEY, PK=PRIMARY KEY, UV=UNIQUE

CREATE TABLE nemori_connection_pool (
    connection_id INT PRIMARY KEY,
    connection_name VARCHAR(255) NOT NULL,
    connection_status VARCHAR(50) DEFAULT 'active',
    max_connection_count INT NOT NULL,
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (connection_name)
);

-- =====================================================================
-- SECTION 2: @m Substitution Candidates
-- =====================================================================

CREATE TABLE nemori_connection_pool_manager (
    manager_id INT PRIMARY KEY,
    connection_pool_id INT NOT NULL,
    active_connection_list TEXT,
    max_connection_count INT NOT NULL DEFAULT 10,
    error_count INT DEFAULT 0,
    total_request_count INT DEFAULT 0,
    FOREIGN KEY (connection_pool_id) REFERENCES nemori_connection_pool(connection_id)
);

-- =====================================================================
-- SECTION 3: @sig Method Signature Dedup (3+ identical SELECT patterns)
-- =====================================================================

-- Query pattern 1
SELECT
    cpm.manager_id,
    cpm.connection_pool_id,
    cpm.active_connection_list,
    cpm.max_connection_count,
    cpm.error_count,
    cpm.total_request_count
FROM nemori_connection_pool_manager cpm
WHERE cpm.connection_pool_id = 1;

-- Query pattern 2 (same shape)
SELECT
    cpm.manager_id,
    cpm.connection_pool_id,
    cpm.active_connection_list,
    cpm.max_connection_count,
    cpm.error_count,
    cpm.total_request_count
FROM nemori_connection_pool_manager cpm
WHERE cpm.connection_pool_id = 2;

-- Query pattern 3 (same shape)
SELECT
    cpm.manager_id,
    cpm.connection_pool_id,
    cpm.active_connection_list,
    cpm.max_connection_count,
    cpm.error_count,
    cpm.total_request_count
FROM nemori_connection_pool_manager cpm
WHERE cpm.connection_pool_id = 3;

-- =====================================================================
-- SECTION 4: Block Dedup (identical subqueries)
-- =====================================================================

-- Subquery 1
SELECT * FROM (
    SELECT
        cp.connection_id,
        cp.connection_name,
        cp.connection_status,
        cpm.active_connection_list,
        cpm.max_connection_count,
        cpm.error_count,
        cpm.total_request_count,
        cp.created_timestamp,
        cp.updated_timestamp
    FROM nemori_connection_pool cp
    JOIN nemori_connection_pool_manager cpm ON cp.connection_id = cpm.connection_pool_id
    WHERE cp.connection_status = 'active'
    ORDER BY cp.created_timestamp DESC
    LIMIT 100
) AS active_connections;

-- Subquery 2 (identical)
SELECT * FROM (
    SELECT
        cp.connection_id,
        cp.connection_name,
        cp.connection_status,
        cpm.active_connection_list,
        cpm.max_connection_count,
        cpm.error_count,
        cpm.total_request_count,
        cp.created_timestamp,
        cp.updated_timestamp
    FROM nemori_connection_pool cp
    JOIN nemori_connection_pool_manager cpm ON cp.connection_id = cpm.connection_pool_id
    WHERE cp.connection_status = 'active'
    ORDER BY cp.created_timestamp DESC
    LIMIT 100
) AS active_connections_backup;

-- Subquery 3 (identical)
SELECT * FROM (
    SELECT
        cp.connection_id,
        cp.connection_name,
        cp.connection_status,
        cpm.active_connection_list,
        cpm.max_connection_count,
        cpm.error_count,
        cpm.total_request_count,
        cp.created_timestamp,
        cp.updated_timestamp
    FROM nemori_connection_pool cp
    JOIN nemori_connection_pool_manager cpm ON cp.connection_id = cpm.connection_pool_id
    WHERE cp.connection_status = 'active'
    ORDER BY cp.created_timestamp DESC
    LIMIT 100
) AS active_connections_report;

-- =====================================================================
-- SECTION 5: Pattern Dictionary Candidates
-- =====================================================================

-- Pattern 1: INSERT with error handling
BEGIN TRANSACTION;
    INSERT INTO nemori_connection_pool (connection_id, connection_name, connection_status, max_connection_count)
    VALUES (100, 'conn_test', 'active', 5);
    IF @@ERROR <> 0
        ROLLBACK TRANSACTION;
    ELSE
        COMMIT TRANSACTION;
END;

-- Pattern 2: INSERT with error handling (repeated pattern)
BEGIN TRANSACTION;
    INSERT INTO nemori_connection_pool_manager (manager_id, connection_pool_id, active_connection_list, max_connection_count)
    VALUES (100, 100, '', 5);
    IF @@ERROR <> 0
        ROLLBACK TRANSACTION;
    ELSE
        COMMIT TRANSACTION;
END;

-- Pattern 3: INSERT with error handling (repeated pattern)
BEGIN TRANSACTION;
    INSERT INTO nemori_connection_pool (connection_id, connection_name, connection_status, max_connection_count)
    VALUES (101, 'conn_test2', 'active', 3);
    IF @@ERROR <> 0
        ROLLBACK TRANSACTION;
    ELSE
        COMMIT TRANSACTION;
END;

-- =====================================================================
-- SECTION 6: Complex JOINs
-- =====================================================================

SELECT
    cp.connection_id,
    cp.connection_name,
    cpm.manager_id,
    cpm.error_count,
    cpm.total_request_count,
    cp.created_timestamp,
    cp.updated_timestamp
FROM nemori_connection_pool cp
INNER JOIN nemori_connection_pool_manager cpm
    ON cp.connection_id = cpm.connection_pool_id
LEFT JOIN nemori_connection_log cl
    ON cp.connection_id = cl.connection_id
LEFT JOIN nemori_connection_metrics cm
    ON cp.connection_id = cm.connection_id
WHERE cp.connection_status = 'active'
    AND cpm.error_count < 100
    AND cpm.total_request_count > 0
ORDER BY cp.created_timestamp DESC;

-- =====================================================================
-- SECTION 7: String Literal Protection
-- =====================================================================

SELECT * FROM nemori_connection_pool
WHERE connection_name = 'active_connection_list should not be aliased'
   OR connection_status = 'max_connection_count in quotes';

-- =====================================================================
-- SECTION 8: Minification Test
-- =====================================================================

-- This comment should be stripped
SELECT /* Block comment */
    connection_id,
    connection_name,
    connection_status
FROM nemori_connection_pool
-- Another comment
WHERE connection_status = 'active';

-- =====================================================================
-- SECTION 9: Window Functions
-- =====================================================================

SELECT
    connection_id,
    connection_name,
    error_count,
    total_request_count,
    ROW_NUMBER() OVER (ORDER BY error_count DESC) as error_rank,
    RANK() OVER (ORDER BY total_request_count DESC) as request_rank,
    SUM(error_count) OVER (ORDER BY created_timestamp) as cumulative_errors,
    AVG(total_request_count) OVER (PARTITION BY connection_status) as avg_requests
FROM nemori_connection_pool_manager cpm
JOIN nemori_connection_pool cp ON cpm.connection_pool_id = cp.connection_id;

-- =====================================================================
-- SECTION 10: Stored Procedure Pattern
-- =====================================================================

CREATE PROCEDURE nemori_get_active_connections
    @connection_pool_id INT,
    @max_results INT = 100
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        cp.connection_id,
        cp.connection_name,
        cp.connection_status,
        cpm.active_connection_list,
        cpm.max_connection_count,
        cpm.error_count,
        cpm.total_request_count,
        cp.created_timestamp,
        cp.updated_timestamp
    FROM nemori_connection_pool cp
    JOIN nemori_connection_pool_manager cpm ON cp.connection_id = cpm.connection_pool_id
    WHERE cp.connection_pool_id = @connection_pool_id
        AND cp.connection_status = 'active'
    ORDER BY cp.created_timestamp DESC
    OFFSET 0 ROWS
    FETCH NEXT @max_results ROWS ONLY;
END;
