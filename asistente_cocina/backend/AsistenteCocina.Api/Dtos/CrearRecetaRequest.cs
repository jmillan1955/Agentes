using AsistenteCocina.Api.Models;

namespace AsistenteCocina.Api.Dtos;

public class CrearRecetaRequest
{
    public string Nombre { get; set; } = string.Empty;
    public string Categoria { get; set; } = string.Empty;
    public int PesoRacion { get; set; }
    public List<Ingrediente> Ingredientes { get; set; } = new();
}

public class ActualizarRecetaRequest
{
    public string Nombre { get; set; } = string.Empty;
    public int PesoRacion { get; set; }
}