// Nemori Engine Test File — TypeScript
// Tests every engine feature that applies to TypeScript code.
//
// Features tested:
//   L1a   minify: strip_inline_comments, collapse_blank_lines, strip_indentation
//   L1b   @m substitution: frequency-ordered aliases
//   L1c   @u import collapse: import { X } from 'module'
//   L1d   @t type aliases: RC, PK, OM, RD, PR, RQ, EX, XT, NN, RT, IT, PM, RG, SY
//   Item8 @b block dedup: identical function bodies
//   @sig  method signature dedup

import { Record, Pick, Omit, Partial, Required, Readonly } from 'typescript';
import { Promise } from 'es6-promise';
import { RegExp } from 'ts-runtime-type-checker';

// =====================================================================
// SECTION 1: @t Type Alias Candidates (TypeScript)
// =====================================================================
// TS @t table: RC=Record, PK=Pick, OM=Omit, RD=Readonly, PR=Partial,
// RQ=Required, EX=Exclude, XT=Extract, NN=NonNullable, RT=ReturnType,
// IT=InstanceType, PM=Promise, RG=RegExp, SY=Symbol

type UserRecord = Record<string, unknown>;
type PartialUser = Partial<UserRecord>;
type RequiredUser = Required<UserRecord>;
type ReadonlyUser = Readonly<UserRecord>;
type UserPick = Pick<UserRecord, 'name' | 'email'>;
type UserOmit = Omit<UserRecord, 'hash'>;

interface UserProfile {
    name: string;
    email: string;
    age: number;
    isActive: boolean;
    metadata: Record<string, unknown>;
}

type UserReturn = ReturnType<typeof createUser>;
type UserInstance = InstanceType<typeof UserService>;

// =====================================================================
// SECTION 2: @u Import Collapse Candidates
// =====================================================================

// =====================================================================
// SECTION 3: @m Substitution Candidates
// =====================================================================

interface ConnectionConfig {
    connectionPoolManager: string;
    maxConnectionCount: number;
    activeConnectionList: string[];
    timeoutDuration: number;
}

class ConnectionPoolManager {
    private activeConnectionList: string[];
    private maxConnectionCount: number;

    constructor(maxConnectionCount: number) {
        this.maxConnectionCount = maxConnectionCount;
        this.activeConnectionList = [];
    }

    initializeConnectionPool(): void {
        for (let i = 0; i < this.maxConnectionCount; i++) {
            const connection = this.createConnection();
            this.activeConnectionList.push(connection);
        }
    }

    private createConnection(): string {
        return `conn_${this.activeConnectionList.length}`;
    }

    getAllActiveSessions(): string[] {
        return [...this.activeConnectionList];
    }

    shutdownConnectionPool(): void {
        this.activeConnectionList = [];
    }
}

// =====================================================================
// SECTION 4: Block Dedup
// =====================================================================

function identicalMethodOne(input: string): string {
    const parsed = parseConnectionString(input);
    const validated = validateParsed(parsed);
    return createPool(validated);
}

function identicalMethodTwo(input: string): string {
    const parsed = parseConnectionString(input);
    const validated = validateParsed(parsed);
    return createPool(validated);
}

function identicalMethodThree(input: string): string {
    const parsed = parseConnectionString(input);
    const validated = validateParsed(parsed);
    return createPool(validated);
}

function parseConnectionString(s: string): string { return s; }
function validateParsed(p: string): string { return p; }
function createPool(v: string): string { return v; }

// =====================================================================
// SECTION 5: @sig Method Signature Dedup
// =====================================================================

function calculateMetric(dataPoint: number, windowSize: number): number {
    return dataPoint * windowSize;
}

function calculateAverage(dataPoint: number, windowSize: number): number {
    return windowSize > 0 ? dataPoint / windowSize : 0;
}

function calculateMaximum(dataPoint: number, windowSize: number): number {
    return Math.max(dataPoint, windowSize);
}

// =====================================================================
// SECTION 6: Lambda / Arrow Function Patterns
// =====================================================================

function applyLambdaOperations(items: [number, string][]): void {
    const mapped1 = items.map(x => x[0]);
    const filtered = items.filter(x => x[0] > 2);
    const sorted = items.sort((a, b) => a[0] - b[0]);
    const mapped2 = items.map(x => x[1]);
}

// SECTION 6b: Lambda Consolidation Test (duplicate arrow functions for @lam)
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

// =====================================================================
// SECTION 7: Generic Type Patterns
// =====================================================================

function processData(input: Map<string, number[]>): Record<string, number[]> {
    const result: Record<string, number[]> = {};
    input.forEach((value, key) => {
        result[key] = value;
    });
    return result;
}

// =====================================================================
// SECTION 8: String Literal Protection
// =====================================================================

function stringLiteralTest(): void {
    const x: string = "active_connection_list should not be aliased";
    const y: string = 'max_connection_count in quotes';
    const z: string = `connection_pool_manager in template literal`;
}

// =====================================================================
// SECTION 9: Minification Test
// =====================================================================

function minificationTest(a: number, b: number): number {
    // This comment should be stripped
    const x = a + b; /* Block comment */
    const y = a - b;
    // Another comment

    const z = x * y;

    return z + x + y;
}

// =====================================================================
// SECTION 10: Large Class (maximize savings)
// =====================================================================

class LargeServiceClass {
    private connectionPoolManager: ConnectionPoolManager;
    private maxRetryCount: number;
    private timeoutDuration: number;
    private activeConnectionList: string[];
    private responseCache: Map<string, string>;
    private errorCount: number;
    private totalRequestCount: number;

    constructor(connectionPoolManager: ConnectionPoolManager, maxRetryCount: number, timeoutSeconds: number) {
        this.connectionPoolManager = connectionPoolManager;
        this.maxRetryCount = maxRetryCount;
        this.timeoutDuration = timeoutSeconds * 1000;
        this.activeConnectionList = [];
        this.responseCache = new Map();
        this.errorCount = 0;
        this.totalRequestCount = 0;
    }

    processConnectionRequest(requestData: string): string | null {
        this.totalRequestCount++;
        if (this.activeConnectionList.length === 0) {
            this.initializeConnectionPool();
        }
        const connection = this.activeConnectionList.pop()!;
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

    private initializeConnectionPool(): void {
        const sessions = this.connectionPoolManager.getAllActiveSessions();
        for (let i = 0; i < sessions.length; i++) {
            this.activeConnectionList.push(`conn_${i}`);
        }
    }

    private sendRequest(connection: string, requestData: string): string {
        return `response_${requestData}`;
    }

    getStatistics(): Record<string, number> {
        return {
            total_requests: this.totalRequestCount,
            errors: this.errorCount,
            cache_size: this.responseCache.size,
            active_connections: this.activeConnectionList.length,
        };
    }
}

function createUser(name: string, email: string): UserProfile {
    return { name, email, age: 0, isActive: true, metadata: {} };
}

class UserService {
    getUser(id: string): UserProfile | null {
        return null;
    }
}
