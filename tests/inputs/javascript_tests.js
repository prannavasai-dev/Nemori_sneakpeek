// Nemori Engine Test File — JavaScript
// Tests every engine feature that applies to JavaScript code.
//
// Features tested:
//   L0.5  preprocess: none specific to JS
//   L1a   minify: strip_block_comments, strip_inline_comments, collapse_blank_lines, strip_indentation
//   L1b   @m substitution: frequency-ordered aliases
//   L1c   @u import collapse: import ... from
//   L1d   @t type aliases: PN, AK, FK, RQ, PR, SP, AR, OB, NM, ST, IT, OT, PT, CL, VL, BX, RG, YL, SY, DM
//   Item8 @b block dedup: identical function bodies
//   @sig  method signature dedup

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { fetch, post, put, del } from 'axios';
import { EventEmitter } from 'events';
import { promisify } from 'util';

// =====================================================================
// SECTION 1: @t Type Alias Candidates (JavaScript)
// =====================================================================
// JS @t table: PN=Promise, AK=async/await, FK=fetch, RQ=require,
// PR=prototype, SP=setTimeout, AR=Array, OB=Object, NM=Number,
// ST=String, IT=Iterator, OT=Observable, PT=Proxy, CL=class,
// VL=volatile, BX=boxed, RG=RegExp, YL=yield, SY=Symbol, DM=DOM

// =====================================================================
// SECTION 2: @u Import Collapse Candidates
// =====================================================================

// =====================================================================
// SECTION 3: @m Substitution Candidates
// =====================================================================

class ConnectionPoolManager {
    constructor(maxConnectionCount) {
        this.activeConnectionList = [];
        this.maxConnectionCount = maxConnectionCount;
    }

    initializeConnectionPool() {
        for (let i = 0; i < this.maxConnectionCount; i++) {
            const connection = this.createConnection(i);
            this.activeConnectionList.push(connection);
        }
    }

    createConnection(id) {
        return `conn_${id}`;
    }

    getAllActiveSessions() {
        return [...this.activeConnectionList];
    }

    shutdownConnectionPool() {
        this.activeConnectionList = [];
    }
}

// =====================================================================
// SECTION 4: Block Dedup
// =====================================================================

function identicalMethodOne(input) {
    const parsed = parseConnectionString(input);
    const validated = validateParsed(parsed);
    return createPool(validated);
}

function identicalMethodTwo(input) {
    const parsed = parseConnectionString(input);
    const validated = validateParsed(parsed);
    return createPool(validated);
}

function identicalMethodThree(input) {
    const parsed = parseConnectionString(input);
    const validated = validateParsed(parsed);
    return createPool(validated);
}

function parseConnectionString(s) { return s; }
function validateParsed(p) { return p; }
function createPool(v) { return v; }

// =====================================================================
// SECTION 5: @sig Method Signature Dedup
// =====================================================================

function calculateMetric(dataPoint, windowSize) {
    return dataPoint * windowSize;
}

function calculateAverage(dataPoint, windowSize) {
    return windowSize > 0 ? dataPoint / windowSize : 0;
}

function calculateMaximum(dataPoint, windowSize) {
    return Math.max(dataPoint, windowSize);
}

// =====================================================================
// SECTION 6: Pattern Dictionary Candidates
// =====================================================================

function patternAlpha() {
    const manager = new ConnectionPoolManager(10);
    manager.initializeConnectionPool();
    const sessions = manager.getAllActiveSessions();
    return sessions.length === 0 ? 'empty' : sessions[0];
}

function patternBeta() {
    const manager = new ConnectionPoolManager(5);
    manager.initializeConnectionPool();
    const sessions = manager.getAllActiveSessions();
    return sessions.length === 0 ? 'empty' : sessions[0];
}

function patternGamma() {
    const manager = new ConnectionPoolManager(8);
    manager.initializeConnectionPool();
    const sessions = manager.getAllActiveSessions();
    return sessions.length === 0 ? 'empty' : sessions[0];
}

// =====================================================================
// SECTION 7: Lambda / Arrow Function Patterns
// =====================================================================

function applyLambdaOperations(items) {
    const mapped1 = items.map(x => x[0]);
    const filtered = items.filter(x => x[0] > 2);
    const sorted = items.sort((a, b) => a[0] - b[0]);
    const mapped2 = items.map(x => x[1]);
}

// =====================================================================
// SECTION 8: Minification Test
// =====================================================================

function minificationTest(a, b) {
    // This comment should be stripped
    const x = a + b; /* Block comment */
    const y = a - b;
    // Another comment

    const z = x * y;

    return z + x + y;
}

// =====================================================================
// SECTION 9: String Literal Protection
// =====================================================================

function stringLiteralTest() {
    const x = "active_connection_list should not be aliased";
    const y = 'max_connection_count in quotes';
    const z = `connection_pool_manager in template literal`;
}

// =====================================================================
// SECTION 10: Large Class (maximize savings)
// =====================================================================

class LargeServiceClass {
    constructor(connectionPoolManager, maxRetryCount, timeoutSeconds) {
        this.connectionPoolManager = connectionPoolManager;
        this.maxRetryCount = maxRetryCount;
        this.timeoutDuration = timeoutSeconds * 1000;
        this.activeConnectionList = [];
        this.responseCache = new Map();
        this.errorCount = 0;
        this.totalRequestCount = 0;
    }

    processConnectionRequest(requestData) {
        this.totalRequestCount++;
        if (this.activeConnectionList.length === 0) {
            this.initializeConnectionPool();
        }
        const connection = this.activeConnectionList.pop();
        try {
            const response = this.sendRequest(connection, requestData);
            this.responseCache.set(requestData, response);
            return response;
        } catch (e) {
            this.errorCount++;
            console.error(`Request failed: ${e}`);
            return null;
        } finally {
            this.activeConnectionList.push(connection);
        }
    }

    initializeConnectionPool() {
        const sessions = this.connectionPoolManager.getAllActiveSessions();
        for (let i = 0; i < sessions.length; i++) {
            this.activeConnectionList.push(`conn_${i}`);
        }
    }

    sendRequest(connection, requestData) {
        return `response_${requestData}`;
    }

    getStatistics() {
        return {
            total_requests: this.totalRequestCount,
            errors: this.errorCount,
            cache_size: this.responseCache.size,
            active_connections: this.activeConnectionList.length,
        };
    }
}

// =====================================================================
// SECTION 8: Lambda / Arrow Function Consolidation (duplicate arrow functions for @lam)
// =====================================================================

function duplicateLambda1() {
    const items = [1, 2, 3, 4, 5];
    const mapped1 = items.map(x => x * 2);
    const filtered = items.filter(x => x > 2);
    return mapped1.filter(x => x > 5);
}

function duplicateLambda2() {
    const items = [10, 20, 30, 40, 50];
    const mapped1 = items.map(x => x * 2);
    const filtered = items.filter(x => x > 2);
    return mapped1.filter(x => x > 5);
}

function duplicateLambda3() {
    const items = [100, 200, 300, 400, 500];
    const mapped1 = items.map(x => x * 2);
    const filtered = items.filter(x => x > 2);
    return mapped1.filter(x => x > 5);
}

console.log('Nemori JavaScript test file');
