#include <jack/jack.h>
#include <dlfcn.h>
#include <cstdlib>
#include <unistd.h>
extern "C" int jack_activate(jack_client_t *client) {
 auto real=(int(*)(jack_client_t*))dlsym(RTLD_NEXT,"jack_activate");
 if(std::getenv("MBMF_TEST_DELAY_ACTIVATE"))usleep(500000);
 return real(client);
}
