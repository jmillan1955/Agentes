namespace AsistenteCocina.Api.Models;

public class Receta
{
    public int Id { get; set; }
    public string Nombre { get; set; } = string.Empty;
    public string Categoria { get; set; } = string.Empty;
    public List<Ingrediente> Ingredientes { get; set; } = new();
}