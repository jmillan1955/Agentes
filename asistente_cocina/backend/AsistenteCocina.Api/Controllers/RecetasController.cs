// Controllers/RecetasController.cs

using AsistenteCocina.Api.Services;
using Microsoft.AspNetCore.Mvc;
using AsistenteCocina.Api.Dtos;

namespace AsistenteCocina.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class RecetasController : ControllerBase
{
    private readonly JsonRecetasService _jsonRecetasService;

    public RecetasController(JsonRecetasService jsonRecetasService)
    {
        _jsonRecetasService = jsonRecetasService;
    }

    // =========================
    // RECETAS
    // =========================

    [HttpGet]
    public IActionResult Get()
    {
        var recetas = _jsonRecetasService.ObtenerTodasLasRecetas();
 Console.WriteLine($"RECETAS ENCONTRADAS: {recetas.Count}");

    foreach (var receta in recetas)
    {
        Console.WriteLine($"RECETA -> {receta.id} {receta.nombre}");
    }

        return Ok(new
        {
            content = recetas
        });
    }

    [HttpGet("{id:int}")]
    public IActionResult GetById(int id)
    {
        var receta = _jsonRecetasService.ObtenerRecetaPorId(id);

        if (receta is null)
            return NotFound();

        return Ok(receta);
    }

    [HttpGet("por-categoria")]
    public IActionResult GetByCategoria([FromQuery] string categoria)
    {
        return Ok(_jsonRecetasService.ObtenerRecetasPorCategoria(categoria));
    }

    [HttpPost]
    public IActionResult Crear([FromBody] CrearRecetaRequest request)
    {
        var receta = _jsonRecetasService.CrearReceta(
            request.Nombre,
            request.Categoria,
            request.PesoRacion
        );

        return Ok(receta);
    }

    [HttpPut("{id:int}")]
    public IActionResult Actualizar(
        int id,
        [FromBody] ActualizarRecetaRequest request)
    {
        var recetaActual = _jsonRecetasService.ObtenerRecetaPorId(id);

        if (recetaActual is null)
            return NotFound();

        _jsonRecetasService.ActualizarReceta(
            id,
            request.Nombre,
            recetaActual.categoria,
            request.PesoRacion
        );

        return Ok();
    }
    
    [HttpDelete("{id:int}")]
    public IActionResult Eliminar(int id)
    {
        _jsonRecetasService.EliminarReceta(id);

        return Ok();
    }

    // =========================
    // INGREDIENTES
    // =========================

    [HttpGet("{id:int}/ingredientes")]
    public IActionResult ObtenerIngredientes(int id)
    {
        var ingredientes = _jsonRecetasService.ObtenerIngredientes(id);

        return Ok(new
        {
            content = ingredientes
        });
    }

    [HttpPost("{id:int}/ingredientes")]
    public IActionResult AgregarIngrediente(
        int id,
        [FromBody] CrearIngredienteRequest request)
    {
        _jsonRecetasService.AgregarIngrediente(id, request);

        return Ok();
    }

    // =========================
    // PASOS
    // =========================

    [HttpGet("{id:int}/pasos")]
    public IActionResult ObtenerPasos(int id)
    {

        var pasos = _jsonRecetasService.ObtenerPasos(id);

        return Ok(new
        {
            content = pasos
        });




    }

    [HttpPost("{id:int}/pasos")]
    public IActionResult AgregarPaso(
        int id,
        [FromBody] PasoDto paso)
    {
        _jsonRecetasService.AgregarPaso(id, paso);

        return Ok();
    }

    // =========================
    // ELABORACIÓN
    // =========================

    [HttpGet("{id:int}/elaboracion")]
    public IActionResult ObtenerElaboracion(int id)
    {
        var contenido = _jsonRecetasService.ObtenerElaboracionReceta(id);

        if (contenido is null)
            return NotFound();

        return Ok(contenido);
    }

    [HttpPut("{id:int}/ingredientes")]
    public IActionResult ActualizarIngrediente(
        int id,
        [FromQuery] string nombreOriginal,
        [FromBody] CrearIngredienteRequest request)
    {
        _jsonRecetasService.ActualizarIngrediente(id, nombreOriginal, request);
        return Ok();
    }

    [HttpPut("{id:int}/pasos/{orden:int}")]
    public IActionResult ActualizarPaso(
        int id,
        int orden,
        [FromBody] PasoDto paso)
    {
        _jsonRecetasService.ActualizarPaso(id, orden, paso);
        return Ok();
    }

    [HttpDelete("{id:int}/pasos/{orden:int}")]
    public IActionResult EliminarPaso(int id, int orden)
    {
        _jsonRecetasService.EliminarPaso(id, orden);
        return Ok();
    }


    [HttpDelete("{id:int}/ingredientes")]
    public IActionResult EliminarIngrediente(
        int id,
        [FromQuery] string nombre)
    {
        _jsonRecetasService.EliminarIngrediente(id, nombre);

        return Ok();
    }
}