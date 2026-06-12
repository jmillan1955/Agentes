from agente_familia.src.tools import solicitar_actualizacion_ubicacion


if __name__ == "__main__":
    persona = "José"

    for modo in ["sensors", "location", "ambos"]:
        print()
        print("=" * 50)
        print(f"Probando {persona} modo={modo}")
        print("=" * 50)

        resultado = solicitar_actualizacion_ubicacion(persona, modo=modo)

        print(f"Resultado {modo}: {resultado}")