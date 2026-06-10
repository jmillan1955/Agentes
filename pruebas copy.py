# ¿Está Casa vacía?

# ¿Está Casa Jessi vacía?




# ¿Dónde está la familia?

# ¿Dónde está cada uno?




from agente_familia.src.models import PERSONAS, HOGARES

print("Personas:")
print(PERSONAS)

print()
print("Hogares:")
print(HOGARES)


print(PERSONAS["José"])




from common.ha_client import HomeAssistantClient

ha = HomeAssistantClient()

estado = ha.get_state("person.jose")

print("Entidad:", estado["entity_id"])
print("Estado:", estado["state"])
print("Atributos:", estado["attributes"])





from common.ha_client import HomeAssistantClient
from agente_familia.src.models import PERSONAS

ha = HomeAssistantClient()

for nombre, entity_id in PERSONAS.items():

    estado = ha.get_state(entity_id)

    print()
    print(f"{nombre}")
    print(f"Entidad : {entity_id}")
    print(f"Estado  : {estado['state']}")



    from agente_familia.src.tools import leer_familia


familia = leer_familia()

for persona in familia:
    print()
    print(persona["nombre"])
    print("Estado:", persona["estado"])
    print("Tracker:", persona["tracker"])
    print("GPS:", persona["latitud"], persona["longitud"])
    print("Última actualización:", persona["ultima_actualizacion"])



    from agente_familia.src.tools import esta_hogar_vacio

for hogar in ["Casa", "Casa Jessi"]:
    resultado = esta_hogar_vacio(hogar)

    print()
    print(resultado["hogar"])

    if resultado["vacio"]:
        print("Está vacía")
    else:
        print("No está vacía")
        print("Presentes:", ", ".join(resultado["presentes"]))




from agente_familia.src.tools import generar_informe_familia

print(generar_informe_familia())        