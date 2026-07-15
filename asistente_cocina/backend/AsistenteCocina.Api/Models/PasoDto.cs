// Models/PasoDto.cs

namespace AsistenteCocina.Api;

public class PasoDto
{
    public int orden { get; set; }

    public string nombre { get; set; } = string.Empty;

    public int duracion { get; set; }

    public string sonido { get; set; } = "Alerta";

    public List<object> operaciones { get; set; } = [];
}