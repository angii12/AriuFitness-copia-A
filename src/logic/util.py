import os
import numpy as np

# Definisci la base a seconda dell'ambiente
if os.path.exists('/content/drive'):
    # Siamo su Google Colab
    BASE_PATH = '/content/drive/MyDrive/AriuFitness'
else:
    # Siamo sul PC locale (aggiusta questo percorso se necessario)
    BASE_PATH = 'C:/Users/renat/Documents/Git/AriuFitness'

def getModelsPath():
    """
    Funzione che restituisce il percorso della cartella dei modelli

    Returns:
        str: il percorso della cartella dei modelli
    """

    return os.path.join(BASE_PATH, "models")

def calculate_angle(a, b, c):
    """
    Calcola l'angolo tra tre punti.
    Questa versione è corretta per gli oggetti NormalizedLandmark di MediaPipe.
    """
    # Usa la notazione con il punto (.x, .y) per leggere le coordinate
    # invece delle parentesi quadre (['x'], ['y']).
    # CORRETTO: Modificato per accedere ai valori 'x' e 'y' da un dizionario.
    a = np.array([a['x'], a['y']])
    b = np.array([b['x'], b['y']])
    c = np.array([c['x'], c['y']])

    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.abs(radians * 180.0 / np.pi)

    if angle > 180.0:
        angle = 360 - angle

    return angle