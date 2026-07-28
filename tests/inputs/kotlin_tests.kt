// Nemori Engine Test File — Kotlin
// Tests every engine feature that applies to Kotlin code.
//
// Features tested:
//   L1a   minify: strip_block_comments, strip_inline_comments, collapse_blank_lines, strip_indentation
//   L1b   @m substitution: frequency-ordered aliases
//   L1c   @u import collapse: import statements
//   L1d   @t type aliases: DF, CR, FL, CP, JP, RS, ST, IT, CT, NM, SC, VL, BX, RG, YL, SY
//   Item8 @b block dedup: identical function bodies

package com.nemori.test

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.channels.*
import kotlinx.serialization.*
import kotlinx.serialization.json.*
import io.ktor.client.*
import io.ktor.client.request.*
import io.ktor.client.statement.*
import org.slf4j.LoggerFactory

// =====================================================================
// SECTION 1: @t Type Alias Candidates (Kotlin)
// =====================================================================
// Kotlin @t table: DF=Deferred, CR=CoroutineScope, FL=Flow, CP=Channel,
// JP=JsonPrimitive, RS=ReceiveChannel, ST=String, IT=Iterator, CT=Callable,
// NM=Number, SC=Scope, VL=volatile, BX=box, RG=Regex, YL=yield, SY=Symbol

typealias ConnectionPoolManagerType = MutableMap<String, MutableList<String>>
typealias StringList = List<String>
typealias IntMap = Map<String, Int>

// =====================================================================
// SECTION 2: @u Import Collapse Candidates
// =====================================================================

// =====================================================================
// SECTION 3: @m Substitution Candidates
// =====================================================================

class ConnectionPoolManager(private val maxConnectionCount: Int) {
    private val activeConnectionList = mutableListOf<String>()
    private val mutex = Any()

    fun initializeConnectionPool() {
        synchronized(mutex) {
            for (i in 0 until maxConnectionCount) {
                val connection = createConnection(i)
                activeConnectionList.add(connection)
            }
        }
    }

    private fun createConnection(id: Int): String = "conn_$id"

    fun getAllActiveSessions(): List<String> {
        synchronized(mutex) {
            return activeConnectionList.toList()
        }
    }

    fun shutdownConnectionPool() {
        synchronized(mutex) {
            activeConnectionList.clear()
        }
    }
}

// =====================================================================
// SECTION 4: Block Dedup
// =====================================================================

fun identicalMethodOne(input: String): String {
    val parsed = parseConnectionString(input)
    val validated = validateParsed(parsed)
    return createPool(validated)
}

fun identicalMethodTwo(input: String): String {
    val parsed = parseConnectionString(input)
    val validated = validateParsed(parsed)
    return createPool(validated)
}

fun identicalMethodThree(input: String): String {
    val parsed = parseConnectionString(input)
    val validated = validateParsed(parsed)
    return createPool(validated)
}

fun parseConnectionString(s: String): String = s
fun validateParsed(p: String): String = p
fun createPool(v: String): String = v

// =====================================================================
// SECTION 5: @sig Method Signature Dedup
// =====================================================================

fun calculateMetric(dataPoint: Double, windowSize: Int): Int {
    return (dataPoint * windowSize).toInt()
}

fun calculateAverage(dataPoint: Double, windowSize: Int): Int {
    return if (windowSize > 0) (dataPoint / windowSize).toInt() else 0
}

fun calculateMaximum(dataPoint: Double, windowSize: Int): Int {
    val a = dataPoint.toInt()
    return if (a > windowSize) a else windowSize
}

// =====================================================================
// SECTION 6: Pattern Dictionary Candidates
// =====================================================================

fun patternAlpha(): String {
    val manager = ConnectionPoolManager(10)
    manager.initializeConnectionPool()
    val sessions = manager.getAllActiveSessions()
    return if (sessions.isEmpty()) "empty" else sessions[0]
}

fun patternBeta(): String {
    val manager = ConnectionPoolManager(5)
    manager.initializeConnectionPool()
    val sessions = manager.getAllActiveSessions()
    return if (sessions.isEmpty()) "empty" else sessions[0]
}

fun patternGamma(): String {
    val manager = ConnectionPoolManager(8)
    manager.initializeConnectionPool()
    val sessions = manager.getAllActiveSessions()
    return if (sessions.isEmpty()) "empty" else sessions[0]
}

// =====================================================================
// SECTION 7: Coroutine Patterns
// =====================================================================

suspend fun coroutineTest(urls: List<String>): List<String> = coroutineScope {
    urls.map { url ->
        async {
            delay(100)
            "fetched_$url"
        }
    }.awaitAll()
}

// =====================================================================
// SECTION 8: Minification Test
// =====================================================================

fun minificationTest(a: Int, b: Int): Int {
    // This comment should be stripped
    val x = a + b; /* Block comment */
    val y = a - b;
    // Another comment

    val z = x * y;

    return z + x + y
}

// =====================================================================
// SECTION 9: String Literal Protection
// =====================================================================

fun stringLiteralTest() {
    val x = "active_connection_list should not be aliased"
    val y = "max_connection_count in quotes"
}

// =====================================================================
// SECTION 10: Large Class (maximize savings)
// =====================================================================

class LargeServiceClass(
    private val connectionPoolManager: ConnectionPoolManager,
    private val maxRetryCount: Int,
    private val timeoutSeconds: Int
) {
    private val activeConnectionList = mutableListOf<String>()
    private val responseCache = mutableMapOf<String, String>()
    private var errorCount = 0
    private var totalRequestCount = 0

    fun processConnectionRequest(requestData: String): String? {
        totalRequestCount++
        if (activeConnectionList.isEmpty()) {
            initializeConnectionPool()
        }
        val connection = activeConnectionList.removeAt(activeConnectionList.size - 1)
        return try {
            val response = sendRequest(connection, requestData)
            responseCache[requestData] = response
            response
        } catch (e: Exception) {
            errorCount++
            null
        } finally {
            activeConnectionList.add(connection)
        }
    }

    private fun initializeConnectionPool() {
        val sessions = connectionPoolManager.getAllActiveSessions()
        for (i in sessions.indices) {
            activeConnectionList.add("conn_$i")
        }
    }

    private fun sendRequest(connection: String, requestData: String): String {
        return "response_$requestData"
    }

    fun getStatistics(): Map<String, Int> {
        return mapOf(
            "total_requests" to totalRequestCount,
            "errors" to errorCount,
            "cache_size" to responseCache.size,
            "active_connections" to activeConnectionList.size
        )
    }
}

}
    }

    // SECTION 9b: Lambda Consolidation Test (duplicate lambdas for @lam)
    fun duplicateLambda1() {
        val items = listOf(1, 2, 3, 4, 5)
        val mapped1 = items.map { x -> x * 2 }
        val filtered = items.filter { x -> x > 2 }
        val mapped1 = items.map { x -> x * 2 }
        val filtered = items.filter { x -> x > 2 }
        return mapped1 + filtered
    }

    fun duplicateLambda2() {
        val items = listOf(10, 20, 30, 40, 50)
        val mapped1 = items.map { x -> x * 2 }
        val filtered = items.filter { x -> x > 2 }
        return mapped1 + filtered
    }

    fun duplicateLambda3() {
        val items = listOf(100, 200, 300, 400, 500)
        val mapped1 = items.map { x -> x * 2 }
        val filtered = items.filter { x -> x > 2 }
        return mapped1 + filtered
    }
}
