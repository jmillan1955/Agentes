// Models/RecetaDto.cs

namespace AsistenteCocina.Api;

public class RecetaDto
{
    public int id { get; set; }

    public string nombre { get; set; } = string.Empty;

    public string categoria { get; set; } = string.Empty;

    public double pesoRacion { get; set; }
}