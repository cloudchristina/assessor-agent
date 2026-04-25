output "artefacts" {
  description = "Map keyed by lambda name to {bucket, key, sha256}"
  value = {
    for name, m in module.package : name => {
      bucket = m.s3_object.bucket
      key    = m.s3_object.key
      sha256 = filebase64sha256(m.local_filename)
    }
  }
}
