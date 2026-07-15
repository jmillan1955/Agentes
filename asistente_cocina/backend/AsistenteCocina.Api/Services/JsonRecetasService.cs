// Services/JsonRecetasService.cs

using System.Text.Json;

namespace AsistenteCocina.Api.Services;

public class JsonRecetasService
{
    private readonly string _dataPath;

    private string RecetasPath => Path.Combine(_dataPath, "recetas.json");
    private string IngredientesPath => Path.Combine(_dataPath, "ingredientes.json");
    private string CronogramasPath => Path.Combine(_dataPath, "cronogramas.json");
    private string ElaboracionesPath => Path.Combine(_dataPath, "Elaboraciones");

    public JsonRecetasService(IConfiguration configuration)
    {
        _dataPath = Path.GetFullPath(
            Path.Combine(
                Directory.GetCurrentDirectory(),
                configuration["DataPath"] ?? "../data"));
    }
    // =========================
    // CATEGORÍAS
    // =========================

    public List<string> ObtenerCategorias()
    {
        return LeerJson<List<RecetaDto>>(RecetasPath)
            .Select(r => r.categoria)
            .Distinct()
            .OrderBy(c => c)
            .ToList();
    }

    public void CrearCategoria(string nombre)
    {
        // Las categorías nacen de las recetas.
    }

    // =========================
    // RECETAS
    // =========================

    public List<RecetaDto> ObtenerTodasLasRecetas()
    {
        Console.WriteLine($"RUTA RECETAS JSON: {RecetasPath}");
        Console.WriteLine($"EXISTE RECETAS JSON: {File.Exists(RecetasPath)}");
        Console.WriteLine($"CONTENIDO RECETAS JSON: {File.ReadAllText(RecetasPath)}");
        
Console.WriteLine($"DATA PATH: {_dataPath}");
Console.WriteLine($"RECETAS PATH: {RecetasPath}");
Console.WriteLine($"EXISTE: {File.Exists(RecetasPath)}");

var recetas = LeerJson<List<RecetaDto>>(RecetasPath);

Console.WriteLine($"NÚMERO DE RECETAS: {recetas.Count}");



        return LeerJson<List<RecetaDto>>(RecetasPath)
            .OrderBy(r => r.categoria)
            .ThenBy(r => r.nombre)
            .ToList();
    }

    public RecetaDto? ObtenerRecetaPorId(int recetaId)
    {
        return LeerJson<List<RecetaDto>>(RecetasPath)
            .FirstOrDefault(r => r.id == recetaId);
    }

    public List<RecetaDto> ObtenerRecetasPorCategoria(string categoria)
    {
        return LeerJson<List<RecetaDto>>(RecetasPath)
            .Where(r => string.Equals(r.categoria, categoria, StringComparison.OrdinalIgnoreCase))
            .OrderBy(r => r.nombre)
            .ToList();
    }

    public RecetaDto CrearReceta(string nombre, string categoria, double pesoRacion)
    {
        var recetas = LeerJson<List<RecetaDto>>(RecetasPath);
        var cronogramas = LeerJson<List<CronogramaDto>>(CronogramasPath);

        var nuevoId = recetas.Count == 0
            ? 1
            : recetas.Max(r => r.id) + 1;

        var receta = new RecetaDto
        {
            id = nuevoId,
            nombre = nombre,
            categoria = categoria,
            pesoRacion = pesoRacion
        };

        recetas.Add(receta);

        cronogramas.Add(new CronogramaDto
        {
            recetaId = nuevoId,
            pasos = []
        });

        GuardarJson(RecetasPath, recetas);
        GuardarJson(CronogramasPath, cronogramas);

        return receta;
    }

    public void ActualizarReceta(int recetaId, string nombre, string categoria, double pesoRacion)
    {
        var recetas = LeerJson<List<RecetaDto>>(RecetasPath);

        var receta = recetas.FirstOrDefault(r => r.id == recetaId);

        if (receta is null)
            return;

        receta.nombre = nombre;
        receta.categoria = categoria;
        receta.pesoRacion = pesoRacion;

        GuardarJson(RecetasPath, recetas);
    }

    public void EliminarReceta(int recetaId)
    {
        var recetas = LeerJson<List<RecetaDto>>(RecetasPath);
        var ingredientes = LeerJson<List<IngredienteDto>>(IngredientesPath);
        var cronogramas = LeerJson<List<CronogramaDto>>(CronogramasPath);

        recetas.RemoveAll(r => r.id == recetaId);
        ingredientes.RemoveAll(i => i.recetaId == recetaId);
        cronogramas.RemoveAll(c => c.recetaId == recetaId);

        GuardarJson(RecetasPath, recetas);
        GuardarJson(IngredientesPath, ingredientes);
        GuardarJson(CronogramasPath, cronogramas);
    }

    // Compatibilidad temporal con código antiguo
    public void RenombrarReceta(string categoria, string nombre, string nuevoNombre, double pesoRacion)
    {
        var recetas = LeerJson<List<RecetaDto>>(RecetasPath);

        var receta = recetas.FirstOrDefault(r =>
            string.Equals(r.categoria, categoria, StringComparison.OrdinalIgnoreCase) &&
            string.Equals(r.nombre, nombre, StringComparison.OrdinalIgnoreCase));

        if (receta is null)
            return;

        receta.nombre = nuevoNombre;
        receta.pesoRacion = pesoRacion;

        GuardarJson(RecetasPath, recetas);
    }

    // =========================
    // INGREDIENTES
    // =========================

    public List<IngredienteDto> ObtenerIngredientes(int recetaId)
    {
        return LeerJson<List<IngredienteDto>>(IngredientesPath)
            .Where(i => i.recetaId == recetaId)
            .ToList();
    }

    public void AgregarIngrediente(int recetaId, CrearIngredienteRequest request)
    {
        var ingredientes = LeerJson<List<IngredienteDto>>(IngredientesPath);

        ingredientes.Add(new IngredienteDto
        {
            recetaId = recetaId,
            cantidad = request.Cantidad,
            unidad = request.Unidad,
            nombre = request.NombreIngrediente
        });

        GuardarJson(IngredientesPath, ingredientes);
    }

    // Compatibilidad temporal con código antiguo
    public List<IngredienteDto> ObtenerIngredientes(string categoria, string nombre)
    {
        var receta = BuscarRecetaPorCategoriaNombre(categoria, nombre);

        if (receta is null)
            return [];

        return ObtenerIngredientes(receta.id);
    }

    // Compatibilidad temporal con código antiguo
    public void AgregarIngrediente(string categoria, string nombre, CrearIngredienteRequest request)
    {
        var receta = BuscarRecetaPorCategoriaNombre(categoria, nombre);

        if (receta is null)
            return;

        AgregarIngrediente(receta.id, request);
    }

    // =========================
    // PASOS / CRONOGRAMA
    // =========================

    public List<PasoDto> ObtenerPasos(int recetaId)
    {
        var cronograma = LeerJson<List<CronogramaDto>>(CronogramasPath)
            .FirstOrDefault(c => c.recetaId == recetaId);

        return cronograma?.pasos ?? [];
    }

    public void AgregarPaso(int recetaId, PasoDto paso)
    {
        var cronogramas = LeerJson<List<CronogramaDto>>(CronogramasPath);

        var cronograma = cronogramas.FirstOrDefault(c => c.recetaId == recetaId);

        if (cronograma is null)
        {
            cronograma = new CronogramaDto
            {
                recetaId = recetaId,
                pasos = []
            };

            cronogramas.Add(cronograma);
        }

        if (paso.orden <= 0)
        {
            paso.orden = cronograma.pasos.Count + 1;
        }

        cronograma.pasos.Add(paso);

        GuardarJson(CronogramasPath, cronogramas);
    }

    // Compatibilidad temporal con código antiguo
    public List<PasoDto> ObtenerPasos(string categoria, string nombre)
    {
        var receta = BuscarRecetaPorCategoriaNombre(categoria, nombre);

        if (receta is null)
            return [];

        return ObtenerPasos(receta.id);
    }

    // Compatibilidad temporal con código antiguo
    public void AgregarPaso(string categoria, string nombre, PasoDto paso)
    {
        var receta = BuscarRecetaPorCategoriaNombre(categoria, nombre);

        if (receta is null)
            return;

        AgregarPaso(receta.id, paso);
    }

    // =========================
    // ELABORACIÓN
    // =========================

    public string? ObtenerElaboracionReceta(int recetaId)
    {
        var ruta = Path.Combine(ElaboracionesPath, $"{recetaId}.md");

        if (!File.Exists(ruta))
            return null;

        return File.ReadAllText(ruta);
    }

    // Compatibilidad temporal con código antiguo
    public string? ObtenerElaboracionReceta(string categoria, string nombre)
    {
        var receta = BuscarRecetaPorCategoriaNombre(categoria, nombre);

        if (receta is null)
            return null;

        return ObtenerElaboracionReceta(receta.id);
    }

    // =========================
    // PRIVADOS
    // =========================

    private RecetaDto? BuscarRecetaPorCategoriaNombre(string categoria, string nombre)
    {
        return LeerJson<List<RecetaDto>>(RecetasPath)
            .FirstOrDefault(r =>
                string.Equals(r.categoria, categoria, StringComparison.OrdinalIgnoreCase) &&
                string.Equals(r.nombre, nombre, StringComparison.OrdinalIgnoreCase));
    }

    private static T LeerJson<T>(string ruta) where T : new()
    {
        if (!File.Exists(ruta))
            return new T();

        var json = File.ReadAllText(ruta);

        if (string.IsNullOrWhiteSpace(json))
            return new T();

        return JsonSerializer.Deserialize<T>(
            json,
            new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            }) ?? new T();
    }

    private static void GuardarJson<T>(string ruta, T datos)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(ruta)!);

        var json = JsonSerializer.Serialize(datos, new JsonSerializerOptions
        {
            WriteIndented = true
        });

        File.WriteAllText(ruta, json);
    }

    public void ActualizarIngrediente(
        int recetaId,
        string nombreOriginal,
        CrearIngredienteRequest request)
    {
        var ingredientes = LeerJson<List<IngredienteDto>>(IngredientesPath);

        var ingrediente = ingredientes.FirstOrDefault(i =>
            i.recetaId == recetaId &&
            i.nombre.Equals(nombreOriginal, StringComparison.OrdinalIgnoreCase));

        if (ingrediente is null)
            return;

        ingrediente.nombre = request.NombreIngrediente;
        ingrediente.cantidad = request.Cantidad;
        ingrediente.unidad = request.Unidad;

        GuardarJson(IngredientesPath, ingredientes);
    }

    public void EliminarIngrediente(
        int recetaId,
        string nombreIngrediente)
    {
        var ingredientes = LeerJson<List<IngredienteDto>>(IngredientesPath);

        ingredientes = ingredientes
            .Where(i =>
                !(i.recetaId == recetaId &&
                i.nombre.Equals(
                    nombreIngrediente,
                    StringComparison.OrdinalIgnoreCase)))
            .ToList();

        GuardarJson(IngredientesPath, ingredientes);
    }


    public void ActualizarPaso(int recetaId, int orden, PasoDto pasoActualizado)
    {
        var cronogramas = LeerJson<List<CronogramaDto>>(CronogramasPath);

        var cronograma = cronogramas.FirstOrDefault(c => c.recetaId == recetaId);

        if (cronograma is null)
            return;

        var paso = cronograma.pasos.FirstOrDefault(p => p.orden == orden);

        if (paso is null)
            return;

        paso.nombre = pasoActualizado.nombre;
        paso.duracion = pasoActualizado.duracion;
        paso.sonido = pasoActualizado.sonido;
        paso.operaciones = pasoActualizado.operaciones;

        GuardarJson(CronogramasPath, cronogramas);
    }

    public void EliminarPaso(int recetaId, int orden)
    {
        var cronogramas = LeerJson<List<CronogramaDto>>(CronogramasPath);

        var cronograma = cronogramas.FirstOrDefault(c => c.recetaId == recetaId);

        if (cronograma is null)
            return;

        cronograma.pasos.RemoveAll(p => p.orden == orden);

        var nuevoOrden = 1;

        foreach (var paso in cronograma.pasos.OrderBy(p => p.orden))
        {
            paso.orden = nuevoOrden;
            nuevoOrden++;
        }

        GuardarJson(CronogramasPath, cronogramas);
    }



}