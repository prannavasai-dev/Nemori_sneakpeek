// Nemori Engine Test File — Java
// Tests every engine feature that applies to Java code.
//
// Features tested:
//   L0.5  preprocess: strip_namespace (package extraction), strip_access_modifiers
//   L1a   minify: strip_block_comments, strip_inline_comments, collapse_blank_lines, strip_indentation
//   L1b   @m substitution: frequency-ordered aliases
//   L1c   @u import collapse: import X.Y;
//   L1d   @t type aliases: CF, CL, LT, DR, IT, LG, JR, PP, TX, JT, MS, RT, MT, KT, PGE, RSP, REQ, SEC, AUT, MP
//   Item7 @p pattern dictionary: repeated n-grams
//   Item8 @b block dedup: identical method bodies
//   @sig  method signature dedup: repeated signatures
//   @i    idiom dictionary (Java-specific patterns)

package com.enterprise.analytics.dataprocessing;

import java.util.List;
import java.util.Map;
import java.util.HashMap;
import java.util.ArrayList;
import java.util.concurrent.CompletableFuture;
import java.time.LocalDateTime;
import java.time.Duration;
import java.time.Instant;
import java.util.logging.Logger;
import java.util.stream.Collectors;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.security.core.SecurityContext;

public class NemoriJavaTest {

    // =====================================================================
    // SECTION 1: @t Type Alias Candidates (Java)
    // =====================================================================
    // Java @t table: CF=CompletableFuture, CL=Collectors, LT=LocalDateTime,
    // DR=Duration, IT=Instant, LG=Logger, JR=JpaRepository, PP=Properties,
    // TX=TransactionTemplate, JT=JdbcTemplate, MS=JmsTemplate, RT=RedisTemplate,
    // MT=MongoTemplate, KT=KafkaTemplate, PGE=Pageable, RSP=ResponseEntity,
    // REQ=RequestEntity, SEC=SecurityContext, AUT=Authentication, MP=Map.Entry

    private static final Logger logger = Logger.getLogger(NemoriJavaTest.class.getName());

    public CompletableFuture<String> fetchAsyncData(String url) {
        return CompletableFuture.supplyAsync(() -> {
            LocalDateTime start = LocalDateTime.now();
            Instant instant = Instant.now();
            Duration elapsed = Duration.between(start, LocalDateTime.now());
            return "fetched from " + url + " in " + elapsed.toMillis() + "ms";
        });
    }

    public Map<String, Object> createResponse(String data) {
        Map<String, Object> response = new HashMap<>();
        response.put("status", "ok");
        response.put("data", data);
        response.put("timestamp", Instant.now().toString());
        return response;
    }

    // =====================================================================
    // SECTION 2: @u Import Collapse Candidates (3+ import lines)
    // =====================================================================

    public void importHeavyMethod() {
        List<String> list = new ArrayList<>();
        Map<String, Integer> map = new HashMap<>();
        map.put("key", 1);
    }

    // =====================================================================
    // SECTION 3: @m Substitution Candidates
    // =====================================================================

    class ConnectionPoolManager {
        private final List<String> activeConnectionList;
        private final int maxConnectionCount;

        ConnectionPoolManager(int maxConnectionCount) {
            this.maxConnectionCount = maxConnectionCount;
            this.activeConnectionList = new ArrayList<>();
        }

        void initializeConnectionPool() {
            for (int i = 0; i < maxConnectionCount; i++) {
                String connection = createConnection();
                activeConnectionList.add(connection);
            }
        }

        String createConnection() {
            return "conn_" + activeConnectionList.size();
        }

        List<String> getAllActiveSessions() {
            return new ArrayList<>(activeConnectionList);
        }

        void shutdownConnectionPool() {
            for (String connection : activeConnectionList) {
                // Mark closed
            }
            activeConnectionList.clear();
        }
    }

    // =====================================================================
    // SECTION 4: Block Dedup (identical method bodies)
    // =====================================================================

    public String identicalMethodOne(String input) {
        String parsed = parseConnectionString(input);
        String validated = validateParsed(parsed);
        return createPool(validated);
    }

    public String identicalMethodTwo(String input) {
        String parsed = parseConnectionString(input);
        String validated = validateParsed(parsed);
        return createPool(validated);
    }

    public String identicalMethodThree(String input) {
        String parsed = parseConnectionString(input);
        String validated = validateParsed(parsed);
        return createPool(validated);
    }

    private String parseConnectionString(String s) { return s; }
    private String validateParsed(String p) { return p; }
    private String createPool(String v) { return v; }

    // =====================================================================
    // SECTION 5: @sig Method Signature Dedup (3+ identical signatures)
    // =====================================================================

    public int calculateMetric(double dataPoint, int windowSize) {
        return (int) (dataPoint * windowSize);
    }

    public int calculateAverage(double dataPoint, int windowSize) {
        return windowSize > 0 ? (int) (dataPoint / windowSize) : 0;
    }

    public int calculateMaximum(double dataPoint, int windowSize) {
        return Math.max((int) dataPoint, windowSize);
    }

    // =====================================================================
    // SECTION 6: Pattern Dictionary Candidates
    // =====================================================================

    public String patternAlpha() {
        ConnectionPoolManager manager = new ConnectionPoolManager(10);
        List<String> sessions = manager.getAllActiveSessions();
        return sessions.isEmpty() ? "empty" : sessions.get(0);
    }

    public String patternBeta() {
        ConnectionPoolManager manager = new ConnectionPoolManager(5);
        List<String> sessions = manager.getAllActiveSessions();
        return sessions.isEmpty() ? "empty" : sessions.get(0);
    }

    public String patternGamma() {
        ConnectionPoolManager manager = new ConnectionPoolManager(8);
        List<String> sessions = manager.getAllActiveSessions();
        return sessions.isEmpty() ? "empty" : sessions.get(0);
    }

    // =====================================================================
    // SECTION 7: try-catch blocks
    // =====================================================================

    public String tryCatchBlock() {
        try {
            String data = "test";
            return data.toUpperCase();
        } catch (Exception e) {
            logger.warning("Error: " + e.getMessage());
            return null;
        }
    }

    // =====================================================================
    // SECTION 8: Minification (comments, blank lines)
    // =====================================================================

    public int minificationTest(int a, int b) {
        // This comment should be stripped
        int x = a + b; /* Block comment */
        int y = a - b;
        // Inline comment

        int z = x * y;

        return z + x + y;
    }

    // =====================================================================
    // SECTION 9: String Literal Protection
    // =====================================================================

    public void stringLiteralTest() {
        String x = "active_connection_list should not be aliased";
        String y = "max_connection_count in quotes";
    }

    // =====================================================================
    // SECTION 10: Large Class (maximize savings)
    // =====================================================================

    class LargeServiceClass {
        private final ConnectionPoolManager connectionPoolManager;
        private final int maxRetryCount;
        private final Duration timeoutDuration;
        private final List<String> activeConnectionList;
        private final Map<String, String> responseCache;
        private int errorCount;
        private int totalRequestCount;

        LargeServiceClass(ConnectionPoolManager connectionPoolManager, int maxRetryCount, int timeoutSeconds) {
            this.connectionPoolManager = connectionPoolManager;
            this.maxRetryCount = maxRetryCount;
            this.timeoutDuration = Duration.ofSeconds(timeoutSeconds);
            this.activeConnectionList = new ArrayList<>();
            this.responseCache = new HashMap<>();
            this.errorCount = 0;
            this.totalRequestCount = 0;
        }

        public String processConnectionRequest(String requestData) {
            totalRequestCount++;
            if (activeConnectionList.isEmpty()) {
                initializeConnectionPool();
            }
            String connection = activeConnectionList.remove(0);
            try {
                String response = sendRequest(connection, requestData);
                responseCache.put(requestData, response);
                return response;
            } catch (Exception e) {
                errorCount++;
                logger.warning("Request failed: " + e.getMessage());
                return null;
            } finally {
                activeConnectionList.add(connection);
            }
        }

        private void initializeConnectionPool() {
            for (int i = 0; i < connectionPoolManager.getAllActiveSessions().size(); i++) {
                activeConnectionList.add("conn_" + i);
            }
        }

        private String sendRequest(String connection, String requestData) {
            return "response_" + requestData;
        }

        public Map<String, Object> getStatistics() {
            Map<String, Object> stats = new HashMap<>();
            stats.put("total_requests", totalRequestCount);
            stats.put("errors", errorCount);
            stats.put("cache_size", responseCache.size());
            stats.put("active_connections", activeConnectionList.size());
            return stats;
        }
    }
}

// SECTION 9b: Lambda Consolidation Test (duplicate lambdas for @lam)
public int duplicateLambda1() {
    List<Integer> items = List.of(1, 2, 3, 4, 5);
    int mapped1 = items.stream().map(x -> x * 2).reduce(0, Integer::sum);
    int filtered = items.stream().filter(x -> x > 2).reduce(0, Integer::sum);
    return mapped1 + filtered;
}

public int duplicateLambda2() {
    List<Integer> items = List.of(10, 20, 30, 40, 50);
    int mapped1 = items.stream().map(x -> x * 2).reduce(0, Integer::sum);
    int filtered = items.stream().filter(x -> x > 2).reduce(0, Integer::sum);
    return mapped1 + filtered;
}

public int duplicateLambda3() {
    List<Integer> items = List.of(100, 200, 300, 400, 500);
    int mapped1 = items.stream().map(x -> x * 2).reduce(0, Integer::sum);
    int filtered = items.stream().filter(x -> x > 2).reduce(0, Integer::sum);
    return mapped1 + filtered;
}
}
