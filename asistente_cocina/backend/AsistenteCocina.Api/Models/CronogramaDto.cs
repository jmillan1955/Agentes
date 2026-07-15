// Models/CronogramaDto.cs

namespace AsistenteCocina.Api;

public class CronogramaDto
{
    public int recetaId { get; set; }

    public List<PasoDto> pasos { get; set; } = [];
}