// Models/IngredienteDto.cs

namespace AsistenteCocina.Api;

public class IngredienteDto
{
    public int recetaId { get; set; }

    public double cantidad { get; set; }

    public string unidad { get; set; } = "%";

    public string nombre { get; set; } = string.Empty;
}