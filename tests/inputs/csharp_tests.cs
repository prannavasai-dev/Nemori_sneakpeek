// Nemori Engine Test File — C#
// Tests every engine feature that applies to C# code.
//
// Features tested:
//   L0.5  preprocess: strip_namespace, strip_access_modifiers, apply_property_shorthand, expand_expression_bodies
//   L1a   minify: strip_block_comments, strip_inline_comments, collapse_blank_lines, strip_indentation
//   L1b   @m substitution: frequency-ordered aliases, collision guard, method guard, string literal protection
//   L1c   @u import collapse: using X;
//   L1d   @t type aliases: CT, CD, JS, JO, SW, TS, SC, HC, IL, DS, IR, etc.
//   L1e   @g generic inference: Dictionary<string, List<int>> etc.
//   Item7 @p pattern dictionary: repeated n-grams
//   Item8 @b block dedup: identical method bodies
//   Item16 @i idiom dictionary: g0, p0-p2, t0, t1, e0, l0-l3
//   @sig  method signature dedup: repeated method signatures
//   @lam  lambda consolidation: repeated lambda expressions
//   @n    namespace strip + dedent

using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using System.Threading;
using System.Text.Json;
using System.Net.Http;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.DependencyInjection;

namespace Enterprise.Analytics.DataProcessing
{
    // =====================================================================
    // SECTION 1: @t Type Alias Candidates (C#)
    // =====================================================================
    // C# @t table: CT=CancellationToken, CD=ConcurrentDictionary, JS=JsonSerializer,
    // JO=JsonSerializerOptions, SW=Stopwatch, TS=TimeSpan, SC=StringComparison,
    // HC=HttpClient, IL=ILogger, DS=DbSet, IR=IRepository, HX=HttpContext

    public class TypeAliasTestService
    {
        private readonly HttpClient _httpClient;
        private readonly ILogger<TypeAliasTestService> _logger;
        private readonly ConcurrentDictionary<string, JsonSerializerOptions> _optionsCache;

        public TypeAliasTestService(HttpClient httpClient, ILogger<TypeAliasTestService> logger)
        {
            _httpClient = httpClient;
            _logger = logger;
            _optionsCache = new ConcurrentDictionary<string, JsonSerializerOptions>();
        }

        public async Task<string> FetchDataAsync(CancellationToken cancellationToken)
        {
            var response = await _httpClient.GetAsync("https://api.example.com/data", cancellationToken);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadAsStringAsync(cancellationToken);
        }

        public JsonSerializerOptions GetOptions(string key)
        {
            return _optionsCache.GetOrAdd(key, k => new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });
        }

        public TimeSpan MeasureExecution(Func<Task> operation)
        {
            var stopwatch = System.Diagnostics.Stopwatch.StartNew();
            operation().GetAwaiter().GetResult();
            stopwatch.Stop();
            return TimeSpan.FromMilliseconds(stopwatch.ElapsedMilliseconds);
        }
    }

    // =====================================================================
    // SECTION 2: @u Import Collapse Candidates (C# using statements)
    // =====================================================================
    // 3+ using statements → collapse into @u section

    public class ImportCollapseTest
    {
        public void DoWork()
        {
            var list = new List<string>();
            var dict = new Dictionary<string, int>();
            var json = JsonSerializer.Serialize(list);
        }
    }

    // =====================================================================
    // SECTION 3: @n Namespace Strip + Dedent
    // =====================================================================
    // The namespace wrapper should be stripped and stored in @n section

    // Already inside namespace Enterprise.Analytics.DataProcessing

    // =====================================================================
    // SECTION 4: Property Shorthand (@i idiom dict p0-p2)
    // =====================================================================
    // { get; set; } → ~
    // { get; private set; } → ~p
    // { get; init; } → ~i
    // { get; } → ~r

    public class PropertyShorthandTest
    {
        public string Name { get; set; }
        public int Age { get; set; }
        public string Email { get; private set; }
        public string InternalId { get; private set; }
        public DateTime CreatedAt { get; init; }
        public string ReadOnly { get; }
        public string FullAccess { get; set; }
        public int Counter { get; private set; }

        public PropertyShorthandTest()
        {
            Name = "";
            Age = 0;
            Email = "";
            InternalId = Guid.NewGuid().ToString();
            CreatedAt = DateTime.UtcNow;
            ReadOnly = "fixed";
            FullAccess = "";
            Counter = 0;
        }
    }

    // =====================================================================
    // SECTION 5: @m Substitution Candidates (long repeated identifiers)
    // =====================================================================
    //   connection_pool_manager (3x)
    //   active_connection_list (3x)
    //   max_connection_count (2x)
    //   initialize_connection_pool (2x)

    public class ConnectionPoolManager
    {
        private readonly List<string> _activeConnectionList;
        private readonly int _maxConnectionCount;

        public ConnectionPoolManager(int maxConnectionCount)
        {
            _maxConnectionCount = maxConnectionCount;
            _activeConnectionList = new List<string>();
        }

        public void InitializeConnectionPool()
        {
            for (int i = 0; i < _maxConnectionCount; i++)
            {
                var connection = CreateConnection();
                _activeConnectionList.Add(connection);
            }
        }

        private string CreateConnection()
        {
            return $"conn_{_activeConnectionList.Count}";
        }

        public List<string> GetAllActiveSessions()
        {
            return new List<string>(_activeConnectionList);
        }

        public void ShutdownConnectionPool()
        {
            foreach (var connection in _activeConnectionList)
            {
                // Mark as closed
            }
            _activeConnectionList.Clear();
        }
    }

    // =====================================================================
    // SECTION 6: @i Idiom Dictionary Candidates (C#)
    // =====================================================================

    // g0: Guard clause null check
    public string ProcessUserData(object userData)
    {
        if (userData == null)
            return null;
        return userData.ToString();
    }

    // g0 repeated
    public string HandleCallback(object callbackData)
    {
        if (callbackData == null)
            throw new ArgumentNullException(nameof(callbackData));
        return callbackData.ToString();
    }

    // g0 repeated again
    public string TransformResult(object resultData)
    {
        if (resultData == null)
            return string.Empty;
        return resultData.ToString();
    }

    // =====================================================================
    // SECTION 7: Expression Body Expansion (@i idiom dict / technique 5)
    // =====================================================================
    // Type Name() { return expr; } → Type Name() => expr;

    public int GetDouble(int value) { return value * 2; }
    public bool IsValid(string input) { return !string.IsNullOrEmpty(input); }
    public string FormatName(string first, string last) { return $"{first} {last}"; }
    public void LogMessage(string message) { Console.WriteLine(message); }

    // =====================================================================
    // SECTION 8: @sig Method Signature Dedup (3+ identical signatures)
    // =====================================================================

    public int CalculateMetric(double dataPoint, int windowSize)
    {
        return (int)(dataPoint * windowSize);
    }

    public int CalculateAverage(double dataPoint, int windowSize)
    {
        return windowSize > 0 ? (int)(dataPoint / windowSize) : 0;
    }

    public int CalculateMaximum(double dataPoint, int windowSize)
    {
        return Math.Max((int)dataPoint, windowSize);
    }

    // =====================================================================
    // SECTION 9: @lam Lambda Consolidation (3+ identical lambdas)
    // =====================================================================
    // .Where(x => x.Value > 0), .Select(x => x.Name), .OrderBy(x => x.Id)

    public List<string> ApplyLambdaOperations(List<int> items)
    {
        var filtered = items.Where(x => x > 0).ToList();
        var selected = items.Select(x => x.ToString()).ToList();
        var ordered = items.OrderBy(x => x).ToList();
        var filtered2 = items.Where(x => x > 0).ToList();
        var selected2 = items.Select(x => x.ToString()).ToList();
        var ordered2 = items.OrderBy(x => x).ToList();
        return selected;
    }

    // =====================================================================
    // SECTION 10: Block Dedup (identical method bodies)
    // =====================================================================

    public string IdenticalMethodOne(string input)
    {
        var parsed = ParseConnectionString(input);
        var validated = ValidateParsed(parsed);
        return CreatePool(validated);
    }

    public string IdenticalMethodTwo(string input)
    {
        var parsed = ParseConnectionString(input);
        var validated = ValidateParsed(parsed);
        return CreatePool(validated);
    }

    public string IdenticalMethodThree(string input)
    {
        var parsed = ParseConnectionString(input);
        var validated = ValidateParsed(parsed);
        return CreatePool(validated);
    }

    private string ParseConnectionString(string s) => s;
    private string ValidateParsed(string p) => p;
    private string CreatePool(string v) => v;

    // =====================================================================
    // SECTION 11: String Literal Protection
    // =====================================================================

    public void StringLiteralTest()
    {
        var x = "active_connection_list should not be aliased";
        var y = 'max_connection_count in single quotes';
        var z = $@"connection_pool_manager in verbatim string";
    }

    // =====================================================================
    // SECTION 12: try-catch-try-finally Idioms (t0, t1)
    // =====================================================================

    public string TryCatchBlock()
    {
        try
        {
            var data = ProcessUserData(null);
            return data;
        }
        catch (ArgumentNullException ex)
        {
            Console.WriteLine(ex.Message);
            return null;
        }
    }

    public string TryCatchFinallyBlock()
    {
        try
        {
            var result = HandleCallback(new object());
            return result;
        }
        catch (Exception ex)
        {
            Console.WriteLine(ex.Message);
            return null;
        }
        finally
        {
            Console.WriteLine("Cleanup");
        }
    }

    // =====================================================================
    // SECTION 13: LINQ Idiom Patterns (l0-l3)
    // =====================================================================

    public List<string> LINQPatterns(List<int> numbers)
    {
        var where = numbers.Where(x => x > 5).ToList();
        var select = numbers.Select(x => x.ToString()).ToList();
        var orderBy = numbers.OrderBy(x => x).ToList();
        var orderByDesc = numbers.OrderByDescending(x => x).ToList();
        return select;
    }

    // =====================================================================
    // SECTION 14: Equals + GetHashCode Override (e0)
    // =====================================================================

    public class ValueObject
    {
        public int Id { get; set; }
        public string Name { get; set; }

        public override bool Equals(object obj)
        {
            if (obj is not ValueObject other) return false;
            return Id == other.Id && Name == other.Name;
        }

        public override int GetHashCode()
        {
            return HashCode.Combine(Id, Name);
        }
    }

    // =====================================================================
    // SECTION 15: Generic Type Inference Candidates
    // =====================================================================

    public class GenericTestService
    {
        public Dictionary<string, List<int>> ProcessData(List<Dictionary<string, int>> input)
        {
            var result = new Dictionary<string, List<int>>();
            foreach (var dict in input)
            {
                foreach (var kvp in dict)
                {
                    if (!result.ContainsKey(kvp.Key))
                        result[kvp.Key] = new List<int>();
                    result[kvp.Key].Add(kvp.Value);
                }
            }
            return result;
        }

        public Dictionary<string, Dictionary<int, string>> NestedGenericTest()
        {
            return new Dictionary<string, Dictionary<int, string>>();
        }
    }

    // =====================================================================
    // SECTION 16: Minification Test (comments, blank lines, indentation)
    // =====================================================================

    public class MinificationTest
    {
        // This comment should be stripped
        public int Calculate(int a, int b)
        {
            /* Block comment
               should be stripped */
            int x = a + b; // inline comment
            int y = a - b;

            int z = x * y;

            return z + x + y;
        }
    }

    // =====================================================================
    // SECTION 17: Large Class (maximize @m savings)
    // =====================================================================

    public class LargeServiceClass
    {
        private readonly ConnectionPoolManager _connectionPoolManager;
        private readonly int _maxRetryCount;
        private readonly TimeSpan _timeoutDuration;
        private readonly List<string> _activeConnectionList;
        private readonly Queue<string> _requestQueue;
        private readonly Dictionary<string, string> _responseCache;
        private int _errorCount;
        private int _totalRequestCount;

        public LargeServiceClass(ConnectionPoolManager connectionPoolManager, int maxRetryCount, int timeoutSeconds)
        {
            _connectionPoolManager = connectionPoolManager;
            _maxRetryCount = maxRetryCount;
            _timeoutDuration = TimeSpan.FromSeconds(timeoutSeconds);
            _activeConnectionList = new List<string>();
            _requestQueue = new Queue<string>();
            _responseCache = new Dictionary<string, string>();
            _errorCount = 0;
            _totalRequestCount = 0;
        }

        public string ProcessConnectionRequest(string requestData)
        {
            _totalRequestCount++;
            if (_activeConnectionList.Count == 0)
                InitializeConnectionPool();
            var connection = _activeConnectionList[0];
            _activeConnectionList.RemoveAt(0);
            try
            {
                var response = SendRequest(connection, requestData);
                _responseCache[requestData] = response;
                return response;
            }
            catch (Exception)
            {
                _errorCount++;
                return null;
            }
            finally
            {
                _activeConnectionList.Add(connection);
            }
        }

        private void InitializeConnectionPool()
        {
            for (int i = 0; i < _connectionPoolManager.GetAllActiveSessions().Count; i++)
            {
                _activeConnectionList.Add($"conn_{i}");
            }
        }

        private string SendRequest(string connection, string requestData)
        {
            return $"response_{requestData}";
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                ["total_requests"] = _totalRequestCount,
                ["errors"] = _errorCount,
                ["cache_size"] = _responseCache.Count,
                ["active_connections"] = _activeConnectionList.Count,
            };
        }
    }
}
