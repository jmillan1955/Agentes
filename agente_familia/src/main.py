from agente_familia.src.agent import responder


if __name__ == "__main__":
    print("Agente Familia")
    print("Escribe 'salir' para terminar.")

    while True:
        pregunta = input("\nPregunta: ")

        if pregunta.lower() in ["salir", "exit", "q"]:
            break

        respuesta = responder(pregunta)
        print("\n" + respuesta)