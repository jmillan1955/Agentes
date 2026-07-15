using AsistenteCocina.Api.Services;
using Microsoft.AspNetCore.Mvc;

namespace AsistenteCocina.Api.Controllers;

[ApiController]
[Route("api/categorias")]
public class CategoriasController(JsonRecetasService jsonRecetasService) : ControllerBase
{
    private readonly JsonRecetasService _jsonRecetasService = jsonRecetasService;

    [HttpGet]
    public IActionResult GetAll()
    {
        var categorias = _jsonRecetasService.ObtenerCategorias();
        return Ok(categorias);
    }

    [HttpPost]
    public IActionResult AddCategoria([FromBody] CrearCategoriaRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.Nombre))
            return BadRequest("El nombre de la categoría es obligatorio");

        _jsonRecetasService.CrearCategoria(request.Nombre.Trim());

        return Ok();
    }
}

public record CrearCategoriaRequest(string Nombre);