import * as ImagePicker from "expo-image-picker";
import { Directory, File, Paths } from "expo-file-system";

const PHOTOS_DIR_NAME = "paios-photos";

function photosDirectory(): Directory {
  const dir = new Directory(Paths.document, PHOTOS_DIR_NAME);
  if (!dir.exists) {
    dir.create();
  }
  return dir;
}

/**
 * Ouvre l'appareil photo et copie la photo prise dans le stockage permanent
 * de l'application. Une photo restée dans le cache temporaire du téléphone
 * pourrait disparaître avant d'être synchronisée (voir ADR 010) : c'est
 * pour ça qu'on la copie tout de suite, jamais son URI d'origine gardée telle
 * quelle.
 *
 * Retourne `null` si le technicien annule ou refuse la permission caméra.
 */
export async function takePhoto(id: string): Promise<string | null> {
  const permission = await ImagePicker.requestCameraPermissionsAsync();
  if (!permission.granted) {
    return null;
  }

  const result = await ImagePicker.launchCameraAsync({ quality: 0.7 });
  if (result.canceled || result.assets.length === 0) {
    return null;
  }

  const source = new File(result.assets[0].uri);
  const destination = new File(photosDirectory(), `${id}.jpg`);
  await source.copy(destination);
  return destination.uri;
}
